from app.core.i18n import SUPPORTED_LANGUAGES, t


def build_main_menu(lang: str) -> dict:
    rows = [
        [{"text": t("menu_explain", lang)}, {"text": t("menu_solve", lang)}],
        [{"text": t("menu_summary", lang)}, {"text": t("menu_image", lang)}],
        [{"text": t("menu_photo_analysis", lang)}, {"text": t("menu_limit", lang)}],
        [{"text": t("menu_long_text", lang)}, {"text": t("menu_invite", lang)}],
        [{"text": t("menu_subscription", lang)}, {"text": t("menu_language", lang)}],
    ]
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_language_keyboard() -> dict:
    buttons = []
    row = []
    for code, label in SUPPORTED_LANGUAGES.items():
        row.append({"text": label, "callback_data": f"set_lang:{code}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return {"inline_keyboard": buttons}


def build_subscription_keyboard(lang: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": t("plan_button_basic", lang), "callback_data": "set_plan:free"},
                {"text": t("plan_button_student", lang), "callback_data": "set_plan:student"},
            ],
            [
                {"text": t("plan_button_pro", lang), "callback_data": "set_plan:pro"},
            ]
        ]
    }
