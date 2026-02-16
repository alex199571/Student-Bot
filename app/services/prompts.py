from app.core.i18n import t

LANGUAGE_HINT = {
    "uk": "Ukrainian",
    "en": "English",
    "ru": "Russian",
    "kk": "Kazakh",
    "pl": "Polish",
    "es": "Spanish",
}


def action_from_menu_text(text: str, lang: str) -> str | None:
    if text == t("menu_explain", lang):
        return "explain_topic"
    if text == t("menu_solve", lang):
        return "solve_problem"
    if text == t("menu_summary", lang):
        return "short_summary"
    if text == t("menu_long_text", lang):
        return "long_text"
    return None


def is_menu_text(text: str, lang: str) -> bool:
    return text in {
        t("menu_explain", lang),
        t("menu_solve", lang),
        t("menu_summary", lang),
        t("menu_image", lang),
        t("menu_photo_analysis", lang),
        t("menu_long_text", lang),
        t("menu_limit", lang),
        t("menu_invite", lang),
        t("menu_subscription", lang),
        t("menu_language", lang),
    }


def build_llm_prompts(action: str, lang: str, user_input: str) -> tuple[str, str]:
    target_language = LANGUAGE_HINT.get(lang, "English")
    system_prompt = (
        "You are AI Student Bot for school students. "
        f"Always answer strictly in {target_language}. "
        "Be clear, beginner-friendly, and concise. Use bullet points and small steps."
    )

    if action == "explain_topic":
        user_prompt = (
            "Task mode: Explain topic.\n"
            "Explain the following topic for a school student.\n"
            "Include: simple definition, key facts, mini-example, and 3 short quiz questions.\n"
            f"Topic from user: {user_input}"
        )
    elif action == "solve_problem":
        user_prompt = (
            "Task mode: Solve problem.\n"
            "Solve the task step-by-step for a student.\n"
            "Include: what is given, solution steps, final answer, and quick self-check.\n"
            f"Problem from user: {user_input}"
        )
    else:
        if action == "long_text":
            user_prompt = (
                "Task mode: Long text.\n"
                "Create a detailed, structured educational explanation.\n"
                "Use sections with headings, examples, and practical tips.\n"
                f"User request: {user_input}"
            )
            return system_prompt, user_prompt

        user_prompt = (
            "Task mode: Short summary.\n"
            "Summarize the provided text in concise study notes.\n"
            "Include: 5-8 key bullets and 1 short takeaway sentence.\n"
            f"Text from user: {user_input}"
        )

    return system_prompt, user_prompt
