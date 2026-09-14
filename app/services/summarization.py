from app.api.ai.gateway import ai_gateway


SUPPORTED_CONTENT_TYPES = {
    "general",
    "message_thread",
    "field_report",
    "meeting",
}


def validate_content_type(content_type: str) -> str:
    """
    Validate and normalize summarization content type.
    """

    normalized = content_type.strip().lower()

    if normalized not in SUPPORTED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported content type: {content_type}. "
            f"Supported types: "
            f"{', '.join(sorted(SUPPORTED_CONTENT_TYPES))}"
        )

    return normalized


def summarize_text(
    text: str,
    content_type: str = "general",
) -> str:
    """
    Summarize a single piece of content.
    """

    text = text.strip()

    if not text:
        raise ValueError("Text cannot be empty.")

    content_type = validate_content_type(
        content_type
    )

    return ai_gateway.summarize(
        text,
        content_type,
    )


def summarize_batch(
    texts: list[str],
    content_type: str = "field_report",
) -> list[str]:
    """
    Summarize multiple messages/reports/content items.
    """

    if not texts:
        raise ValueError(
            "At least one text item is required."
        )

    content_type = validate_content_type(
        content_type
    )

    cleaned_texts = []

    for text in texts:
        text = text.strip()

        if not text:
            raise ValueError(
                "Batch text items cannot be empty."
            )

        cleaned_texts.append(text)

    return [
        summarize_text(
            text,
            content_type,
        )
        for text in cleaned_texts
    ]