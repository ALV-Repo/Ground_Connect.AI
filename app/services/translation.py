from app.api.ai.gateway import ai_gateway


LANGUAGE_NAMES = {
    "en": "english",
    "en-us": "english",
    "en-in": "english",
    "english": "english",

    "hi": "hindi",
    "hi-in": "hindi",
    "hindi": "hindi",

    "kn": "kannada",
    "kn-in": "kannada",
    "kannada": "kannada",
}


SUPPORTED_TRANSLATION_LANGUAGES = {
    "english",
    "hindi",
    "kannada",
}


def normalize_language(language: str) -> str:
    """
    Convert language code/name to canonical language name.
    """

    if not language or not language.strip():
        raise ValueError(
            "Target language is required."
        )

    key = language.strip().lower()

    if key not in LANGUAGE_NAMES:
        raise ValueError(
            f"Unsupported language: {language}. "
            f"Supported languages: English, Hindi, Kannada."
        )

    return LANGUAGE_NAMES[key]


def translate_text(
    text: str,
    target_language: str,
) -> str:
    """
    Translate text using configured AI gateway.
    """

    text = text.strip()

    if not text:
        raise ValueError(
            "Text cannot be empty."
        )

    normalized_language = normalize_language(
        target_language
    )

    return ai_gateway.translate(
        text,
        normalized_language,
    )


def translation_quality_label() -> str:
    """
    Current mock provider cannot guarantee
    production translation quality.

    Therefore the output is explicitly marked
    as machine-translated.
    """

    return "machine-translated"