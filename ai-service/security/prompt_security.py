import re


class PromptInjectionDetector:
    """
    Detects common prompt-injection and jailbreak patterns
    in user-provided text.
    """

    PATTERNS = [
        # Instruction override attempts
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
            r"\boverride\s+(the\s+)?previous\s+instructions\b",
            re.IGNORECASE,
        ),

        # System/developer prompt extraction
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
        re.compile(
            r"\bprint\s+(your\s+)?(system|developer)\s+prompt\b",
            re.IGNORECASE,
        ),

        # Jailbreak / role-play framing
        re.compile(
            r"\b(?:pretend|act|roleplay|role-play)\s+(?:you\s+are|as)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:you\s+are\s+now|from\s+now\s+on)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:developer|admin|root)\s+mode\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:jailbreak|do\s+anything\s+now|dan\s+mode)\b",
            re.IGNORECASE,
        ),

        # Common non-English instruction-override phrases
        re.compile(
            r"(?:ignore|forget|disregard).{0,30}"
            r"(?:previous|earlier).{0,30}"
            r"(?:instructions|rules)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:మునుపటి|ముందు).{0,30}"
            r"(?:సూచనలు|నిబంధనలు).{0,30}"
            r"(?:విస్మరించు|మర్చిపో)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:पिछली|पहले की).{0,30}"
            r"(?:निर्देश|हिदायत).{0,30}"
            r"(?:भूलो|नज़रअंदाज़ करो)",
            re.IGNORECASE,
        ),
    ]

    def detect(self, text: str) -> bool:
        if not text:
            return False

        normalized_text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        return any(
            pattern.search(normalized_text)
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