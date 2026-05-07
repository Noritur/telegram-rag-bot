LANG_LABELS = {"uk": "Ukrainian", "ru": "Russian", "en": "English"}

HANDOFF = {
    "uk": "Цього у нас зараз нема — передам ваше питання власниці, вона напише особисто.",
    "ru": "Этого у нас сейчас нет — передам ваш вопрос владелице, она напишет лично.",
    "en": "We don't have this right now — I'll pass your question to the owner, she'll get back to you personally.",
}

LLM_ERROR = {
    "uk": "Технічна заминка — спробуйте ще раз за хвилину.",
    "ru": "Техническая заминка — попробуйте через минуту.",
    "en": "Hit a technical snag — try again in a minute.",
}


def _format_product(p: dict) -> str:
    head_parts = [p.get("stone"), p.get("color")]
    price = p.get("price_uah")
    if price is not None:
        head_parts.append(f"{price} UAH")
    head = ", ".join(part for part in head_parts if part)
    name = p.get("name", "")
    desc = p.get("description", "")
    return f"- {name} | {head}\n  {desc}"


def build_system_prompt(lang: str, products: list[dict]) -> str:
    lang_label = LANG_LABELS.get(lang, "English")
    catalog_block = (
        "\n".join(_format_product(p) for p in products) if products else "(empty)"
    )
    return (
        "You are a consultant for Murmure, a boutique selling jewelry made of natural stones.\n"
        f"The user is writing in {lang_label}. Respond ONLY in {lang_label}.\n"
        "Use ONLY products listed in the CATALOG section below — do not invent items "
        "or suggest products not present there.\n"
        "Mention stone properties (calming, grounding, protective, etc.) when relevant — "
        "Murmure customers value the spiritual side of stones.\n"
        "Tone: warm, elegant, knowledgeable but not pushy. Concise — 2-4 sentences.\n"
        "If none of the catalog items genuinely match the user's question, "
        "say briefly that you'll connect them to the owner (in the same language).\n"
        "\nCATALOG:\n"
        f"{catalog_block}"
    )
