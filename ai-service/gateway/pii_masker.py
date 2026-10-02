import re


class PIIMasker:
    """
    Masks common personally identifiable information (PII)
    before a prompt is sent to an AI provider.
    """

    PATTERNS = {
        "email": re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),

        "phone": re.compile(
            r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)"
        ),

        "aadhaar": re.compile(
            r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"
        ),

        "aadhaar_context": re.compile(
            r"(?i)\b(?:aadhaar|aadhar|uid)\b"
            r".{0,40}?"
            r"(?P<number>\d{4}[-\s]?\d{4}[-\s]?\d{4})"
        ),
    }

    def mask(self, text: str) -> str:
        if not text:
            return text

        masked_text = text

        masked_text = self.PATTERNS["email"].sub(
            "[EMAIL_REDACTED]",
            masked_text,
        )

        masked_text = self.PATTERNS["phone"].sub(
            "[PHONE_REDACTED]",
            masked_text,
        )

        # Aadhaar numbers are masked only when Aadhaar-related
        # context appears immediately before the number.
        masked_text = self.PATTERNS["aadhaar_context"].sub(
            "[AADHAAR_REDACTED]",
            masked_text,
        )

        return masked_text