import re


class PromptInjectionDetector:
    """
    Detects common prompt-injection patterns
    in user-provided text.
    """

    PATTERNS = [
        re.compile(
            r"\bignore\s+(all\s+)?previous\s+instructions\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bforget\s+(all\s+)?previous\s+instructions\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bdisregard\s+(all\s+)?previous\s+instructions\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(system|developer)\s+message\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\breveal\s+(your\s+)?(system|developer)\s+prompt\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bshow\s+(me\s+)?(your\s+)?(system|developer)\s+prompt\b",
            re.IGNORECASE,
        ),
    ]

    def detect(self, text: str) -> bool:
        if not text:
            return False

        return any(
            pattern.search(text)
            for pattern in self.PATTERNS
        )


class PromptSecurityService:

    def __init__(self):
        self.detector = PromptInjectionDetector()

    def sanitize(self, text: str) -> tuple[str, bool]:
        """
        Detect prompt injection and neutralize the request.

        Returns:
            sanitized_text, injection_detected
        """

        if not text:
            return text, False

        if self.detector.detect(text):
            return (
                "[PROMPT_INJECTION_BLOCKED]",
                True,
            )

        return text, False