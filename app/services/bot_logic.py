from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import FALLBACK_LANGUAGE, SUPPORTED_LANGUAGES, t
from app.db.redis import redis_client
from app.repositories.query_log_repo import QueryLogRepository
from app.repositories.user_repo import UserRepository
from app.schemas.telegram import CallbackQuery, TelegramMessage, TelegramPhotoSize, TelegramUpdate
from app.services.limits import (
    consume_monthly_tokens,
    get_daily_image_usage,
    get_daily_long_text_usage,
    get_daily_photo_analysis_usage,
    get_daily_usage,
    get_plan,
    month_key_now,
    precheck_and_consume_image_request,
    precheck_and_consume_long_text_request,
    precheck_and_consume_photo_analysis_request,
    precheck_and_consume_request,
    rollback_image_request,
    rollback_long_text_request,
    rollback_photo_analysis_request,
    rollback_request,
)
from app.services.llm import LLMService
from app.services.menu import build_language_keyboard, build_main_menu, build_subscription_keyboard
from app.services.prompts import action_from_menu_text, build_llm_prompts, is_menu_text
from app.services.state import clear_pending_action, get_pending_action, set_pending_action
from app.services.telegram_api import TelegramAPI


class BotService:
    def __init__(self, db: AsyncSession, telegram_api: TelegramAPI):
        self.db = db
        self.telegram_api = telegram_api
        self.users = UserRepository(db)
        self.logs = QueryLogRepository(db)
        self.llm = LLMService()

    async def handle_update(self, update: TelegramUpdate) -> None:
        if update.callback_query:
            await self._handle_callback(update.callback_query)
            return

        if update.message:
            await self._handle_message(update.message)

    async def _handle_callback(self, callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            return

        if callback.data.startswith("set_lang:"):
            lang = callback.data.split(":", maxsplit=1)[1]
            if lang not in SUPPORTED_LANGUAGES:
                lang = FALLBACK_LANGUAGE

            user = await self.users.get_or_create(
                telegram_id=callback.from_.id,
                username=callback.from_.username,
                first_name=callback.from_.first_name,
                language=lang,
                month_key=month_key_now(),
            )
            user.language = lang
            await self.users.save(user)
            await self.db.commit()

            await self.telegram_api.answer_callback_query(callback.id)
            await self.telegram_api.send_message(
                chat_id=callback.message.chat.id,
                text=t("start_text", user.language),
                reply_markup=build_main_menu(user.language),
            )
            return

        if callback.data.startswith("set_plan:"):
            plan = callback.data.split(":", maxsplit=1)[1]
            if plan not in {"free", "student", "pro"}:
                return

            preferred_lang = (callback.from_.language_code or "").lower()
            if preferred_lang not in SUPPORTED_LANGUAGES:
                preferred_lang = FALLBACK_LANGUAGE

            user = await self.users.get_or_create(
                telegram_id=callback.from_.id,
                username=callback.from_.username,
                first_name=callback.from_.first_name,
                language=preferred_lang,
                month_key=month_key_now(),
            )
            user.plan = plan
            await self.users.save(user)
            await self.db.commit()

            await self.telegram_api.answer_callback_query(callback.id)
            await self.telegram_api.send_message(
                chat_id=callback.message.chat.id,
                text=t("plan_changed_demo", user.language).format(plan=user.plan),
                reply_markup=build_main_menu(user.language),
            )
            return

    async def _handle_message(self, message: TelegramMessage) -> None:
        text = (message.text or "").strip()
        caption = (message.caption or "").strip()
        tg_user = message.from_

        if not tg_user:
            return

        preferred_lang = (tg_user.language_code or "").lower()
        if preferred_lang not in SUPPORTED_LANGUAGES:
            preferred_lang = "unset"

        user = await self.users.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            language=preferred_lang,
            month_key=month_key_now(),
        )
        if user.plan == "paid":
            user.plan = "pro"

        if user.is_banned:
            await self.db.commit()
            return

        if text.startswith("/start"):
            await clear_pending_action(user.telegram_id)
            await self._handle_start(message.chat.id, user)
            await self.db.commit()
            return

        if text.startswith("/help"):
            await self.telegram_api.send_message(chat_id=message.chat.id, text=t("help_text", user.language))
            await self.db.commit()
            return

        if text.startswith("/cancel"):
            await clear_pending_action(user.telegram_id)
            await self.telegram_api.send_message(chat_id=message.chat.id, text=t("mode_cancelled", user.language))
            await self.db.commit()
            return

        if is_menu_text(text, user.language):
            await clear_pending_action(user.telegram_id)

        if text == t("menu_language", user.language):
            await self.telegram_api.send_message(
                chat_id=message.chat.id,
                text=t("choose_language", user.language),
                reply_markup=build_language_keyboard(),
            )
            await self.db.commit()
            return

        if text == t("menu_long_text", user.language):
            if get_plan(user).name == "free":
                await self.telegram_api.send_message(chat_id=message.chat.id, text=t("long_text_paid_only", user.language))
            else:
                await set_pending_action(user.telegram_id, "await_long_text_input")
                await self.telegram_api.send_message(chat_id=message.chat.id, text=t("request_long_text", user.language))
            await self.db.commit()
            return

        if text == t("menu_limit", user.language):
            await self._send_usage(message.chat.id, user)
            await self.db.commit()
            return

        if text == t("menu_invite", user.language):
            bot_username = "YourBotUsername"
            await self.telegram_api.send_message(
                chat_id=message.chat.id,
                text=t("invite_text", user.language).format(bot_username=bot_username, user_id=user.telegram_id),
            )
            await self.db.commit()
            return

        if text == t("menu_subscription", user.language):
            await self.telegram_api.send_message(
                chat_id=message.chat.id,
                text=t("subscription_catalog", user.language).format(
                    student_price=settings.student_price_usd,
                    pro_price=settings.pro_price_usd,
                ),
                reply_markup=build_subscription_keyboard(user.language),
            )
            await self.db.commit()
            return

        if text == t("menu_image", user.language):
            await self._start_image_flow(chat_id=message.chat.id, user=user)
            await self.db.commit()
            return

        if text == t("menu_photo_analysis", user.language):
            await set_pending_action(user.telegram_id, "await_photo_upload")
            await self.telegram_api.send_message(chat_id=message.chat.id, text=t("photo_analysis_prompt_request", user.language))
            await self.db.commit()
            return

        pending_action = await get_pending_action(user.telegram_id)
        if text and pending_action in {"await_explain_topic_input", "await_solve_problem_input", "await_short_summary_input", "await_long_text_input"}:
            action = pending_action.replace("await_", "").replace("_input", "")
            await self._run_llm_action(chat_id=message.chat.id, user=user, action=action, user_input=text)
            await clear_pending_action(user.telegram_id)
            await self.db.commit()
            return

        if pending_action == "await_image_prompt":
            await self._run_image_action(chat_id=message.chat.id, user=user, image_prompt=text)
            await clear_pending_action(user.telegram_id)
            await self.db.commit()
            return

        if pending_action == "await_photo_upload" and not message.photo:
            await self.telegram_api.send_message(chat_id=message.chat.id, text=t("photo_analysis_prompt_request", user.language))
            await self.db.commit()
            return

        # Photo analysis works with direct photo messages or after choosing menu mode.
        if message.photo:
            await self._run_photo_analysis_action(
                chat_id=message.chat.id,
                user=user,
                photo_sizes=message.photo,
                user_prompt=caption or t("menu_photo_analysis", user.language),
            )
            await clear_pending_action(user.telegram_id)
            await self.db.commit()
            return

        action = action_from_menu_text(text, user.language)
        if action:
            await self._start_text_action_flow(chat_id=message.chat.id, user=user, action=action)
            await self.db.commit()
            return

        await self.telegram_api.send_message(
            chat_id=message.chat.id,
            text=t("start_text", user.language),
            reply_markup=build_main_menu(user.language),
        )
        await self.db.commit()

    async def _start_image_flow(self, chat_id: int, user) -> None:
        if get_plan(user).name != "pro":
            await self.telegram_api.send_message(chat_id=chat_id, text=t("image_paid_only", user.language))
            return

        await set_pending_action(user.telegram_id, "await_image_prompt")
        await self.telegram_api.send_message(chat_id=chat_id, text=t("image_prompt_request", user.language))

    async def _start_text_action_flow(self, chat_id: int, user, action: str) -> None:
        key_map = {
            "explain_topic": "request_explain_topic",
            "solve_problem": "request_solve_problem",
            "short_summary": "request_short_summary",
            "long_text": "request_long_text",
        }
        pending_map = {
            "explain_topic": "await_explain_topic_input",
            "solve_problem": "await_solve_problem_input",
            "short_summary": "await_short_summary_input",
            "long_text": "await_long_text_input",
        }

        request_key = key_map.get(action, "request_explain_topic")
        pending_value = pending_map.get(action, "await_explain_topic_input")
        await set_pending_action(user.telegram_id, pending_value)
        await self.telegram_api.send_message(chat_id=chat_id, text=t(request_key, user.language))

    async def _run_llm_action(self, chat_id: int, user, action: str, user_input: str) -> None:
        system_prompt, user_prompt = build_llm_prompts(action, user.language, user_input=user_input)
        prompt_for_log = f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}"

        long_text_prechecked = False
        if action == "long_text":
            long_text_limit = await precheck_and_consume_long_text_request(redis_client, user)
            if not long_text_limit.allowed:
                if long_text_limit.reason == "long_text_daily":
                    await self.telegram_api.send_message(chat_id=chat_id, text=t("long_text_daily_limit", user.language))
                    status = "long_text_daily_limit"
                elif long_text_limit.reason == "long_text_monthly":
                    await self.telegram_api.send_message(chat_id=chat_id, text=t("long_text_monthly_limit", user.language))
                    status = "long_text_monthly_limit"
                else:
                    await self.telegram_api.send_message(chat_id=chat_id, text=t("long_text_paid_only", user.language))
                    status = "long_text_plan_locked"

                await self.logs.create(
                    telegram_id=user.telegram_id,
                    action=action,
                    plan=user.plan,
                    prompt_text=prompt_for_log,
                    status=status,
                )
                return
            long_text_prechecked = True

        estimated_input_tokens = self.llm.estimate_tokens(prompt_for_log)
        limit_result = await precheck_and_consume_request(redis_client, user, estimated_input_tokens)

        if not limit_result.allowed:
            if action == "long_text" and long_text_prechecked:
                await rollback_long_text_request(redis_client, user)
            if limit_result.reason == "daily":
                await self.telegram_api.send_message(chat_id=chat_id, text=t("limit_reached_daily", user.language))
                status = "limit_daily"
            else:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("limit_reached_monthly", user.language))
                status = "limit_monthly"

            await self.logs.create(
                telegram_id=user.telegram_id,
                action=action,
                plan=user.plan,
                prompt_text=prompt_for_log,
                status=status,
            )
            return

        try:
            llm_result = await self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=limit_result.max_output_tokens,
                lang=user.language,
            )
            await self.telegram_api.send_message(chat_id=chat_id, text=llm_result.text)
            consume_monthly_tokens(user, llm_result.total_tokens)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action=action,
                plan=user.plan,
                prompt_text=prompt_for_log,
                response_text=llm_result.text,
                status="ok",
                input_tokens=llm_result.input_tokens,
                output_tokens=llm_result.output_tokens,
                total_tokens=llm_result.total_tokens,
            )
        except Exception as exc:
            await rollback_request(redis_client, user)
            if action == "long_text" and long_text_prechecked:
                await rollback_long_text_request(redis_client, user)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action=action,
                plan=user.plan,
                prompt_text=prompt_for_log,
                status="error",
                error_message=str(exc)[:500],
            )
            try:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("llm_error", user.language))
            except Exception:
                pass

    async def _run_image_action(self, chat_id: int, user, image_prompt: str) -> None:
        limit_result = await precheck_and_consume_image_request(redis_client, user)
        if not limit_result.allowed:
            if limit_result.reason == "image_plan":
                await self.telegram_api.send_message(chat_id=chat_id, text=t("image_paid_only", user.language))
                status = "image_plan_locked"
            elif limit_result.reason == "image_daily":
                await self.telegram_api.send_message(chat_id=chat_id, text=t("image_daily_limit", user.language))
                status = "image_daily_limit"
            else:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("image_monthly_limit", user.language))
                status = "image_monthly_limit"

            await self.logs.create(
                telegram_id=user.telegram_id,
                action="image_generate",
                plan=user.plan,
                prompt_text=image_prompt,
                status=status,
            )
            return

        try:
            result = await self.llm.generate_image(image_prompt)
            await self.telegram_api.send_photo_bytes(chat_id=chat_id, image_bytes=result.image_bytes)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="image_generate",
                plan=user.plan,
                prompt_text=image_prompt,
                response_text=f"image_model={result.model}",
                status="ok",
            )
        except Exception as exc:
            await rollback_image_request(redis_client, user, used_bonus_credit=limit_result.used_bonus_credit)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="image_generate",
                plan=user.plan,
                prompt_text=image_prompt,
                status="error",
                error_message=str(exc)[:500],
            )
            try:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("image_error", user.language))
            except Exception:
                pass

    async def _run_photo_analysis_action(
        self,
        chat_id: int,
        user,
        photo_sizes: list[TelegramPhotoSize],
        user_prompt: str,
    ) -> None:
        estimated_input_tokens = self.llm.estimate_tokens(user_prompt) + 300
        request_limit = await precheck_and_consume_request(redis_client, user, estimated_input_tokens)
        if not request_limit.allowed:
            if request_limit.reason == "daily":
                await self.telegram_api.send_message(chat_id=chat_id, text=t("limit_reached_daily", user.language))
            else:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("limit_reached_monthly", user.language))
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="photo_analysis",
                plan=user.plan,
                prompt_text=user_prompt,
                status=f"request_{request_limit.reason}",
            )
            return

        photo_limit = await precheck_and_consume_photo_analysis_request(redis_client, user)
        if not photo_limit.allowed:
            await rollback_request(redis_client, user)
            if photo_limit.reason == "photo_daily":
                await self.telegram_api.send_message(chat_id=chat_id, text=t("photo_analysis_daily_limit", user.language))
            else:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("photo_analysis_monthly_limit", user.language))
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="photo_analysis",
                plan=user.plan,
                prompt_text=user_prompt,
                status=f"photo_{photo_limit.reason}",
            )
            return

        largest = max(photo_sizes, key=lambda p: p.file_size or 0)
        try:
            image_url = await self.telegram_api.get_file_download_url(largest.file_id)
            llm_result = await self.llm.analyze_photo(
                image_url=image_url,
                user_prompt=user_prompt,
                max_output_tokens=request_limit.max_output_tokens,
                lang=user.language,
            )
            await self.telegram_api.send_message(chat_id=chat_id, text=llm_result.text)
            consume_monthly_tokens(user, llm_result.total_tokens)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="photo_analysis",
                plan=user.plan,
                prompt_text=user_prompt,
                response_text=llm_result.text,
                status="ok",
                input_tokens=llm_result.input_tokens,
                output_tokens=llm_result.output_tokens,
                total_tokens=llm_result.total_tokens,
            )
        except Exception as exc:
            await rollback_photo_analysis_request(redis_client, user)
            await rollback_request(redis_client, user)
            await self.logs.create(
                telegram_id=user.telegram_id,
                action="photo_analysis",
                plan=user.plan,
                prompt_text=user_prompt,
                status="error",
                error_message=str(exc)[:500],
            )
            try:
                await self.telegram_api.send_message(chat_id=chat_id, text=t("photo_analysis_error", user.language))
            except Exception:
                pass

    async def _handle_start(self, chat_id: int, user) -> None:
        if user.language not in SUPPORTED_LANGUAGES:
            await self.telegram_api.send_message(
                chat_id=chat_id,
                text=t("choose_language", FALLBACK_LANGUAGE),
                reply_markup=build_language_keyboard(),
            )
            return

        await self.telegram_api.send_message(
            chat_id=chat_id,
            text=t("start_text", user.language),
            reply_markup=build_main_menu(user.language),
        )

    async def _send_usage(self, chat_id: int, user) -> None:
        plan = get_plan(user)
        daily_usage = await get_daily_usage(redis_client, user.telegram_id)
        daily_image_usage = await get_daily_image_usage(redis_client, user.telegram_id)
        daily_photo_usage = await get_daily_photo_analysis_usage(redis_client, user.telegram_id)
        daily_long_text_usage = await get_daily_long_text_usage(redis_client, user.telegram_id)

        text = t("usage_text", user.language).format(
            plan=user.plan,
            monthly_requests=user.monthly_requests_used,
            monthly_limit=plan.monthly_requests_limit,
            monthly_tokens=user.monthly_tokens_used,
            tokens_limit=plan.monthly_tokens_limit,
            daily_requests=daily_usage,
            daily_limit=plan.daily_requests_limit,
            monthly_images=user.monthly_images_used,
            monthly_images_limit=plan.monthly_images_limit,
            daily_images=daily_image_usage,
            daily_images_limit=plan.daily_images_limit,
            monthly_photo=user.monthly_photo_analyses_used,
            monthly_photo_limit=plan.monthly_photo_analysis_limit,
            daily_photo=daily_photo_usage,
            daily_photo_limit=plan.daily_photo_analysis_limit,
            monthly_long_text=user.monthly_long_texts_used,
            monthly_long_text_limit=plan.monthly_long_text_limit,
            daily_long_text=daily_long_text_usage,
            daily_long_text_limit=plan.daily_long_text_limit,
        )
        await self.telegram_api.send_message(chat_id=chat_id, text=text)
