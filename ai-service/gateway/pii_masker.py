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

        masked_text = self.PATTERNS["aadhaar"].sub(
            "[AADHAAR_REDACTED]",
            masked_text,
        )

        return masked_text
if __name__ == "__main__":
    masker = PIIMasker()

    test_text = (
        "Citizen Ravi can be contacted at "
        "ravi@example.com or 9876543210. "
        "Aadhaar: 1234 5678 9012."
    )

    print("Original:")
    print(test_text)

    print("\nMasked:")
    print(masker.mask(test_text))