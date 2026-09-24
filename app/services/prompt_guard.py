import re


PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?previous\s+instructions\b",
    r"\bignore\s+(all\s+)?prior\s+instructions\b",
    r"\bdisregard\s+(all\s+)?previous\s+instructions\b",
    r"\bforget\s+(all\s+)?previous\s+instructions\b",
    r"\bshow\s+me\s+(district|tenant|branch)\s+[a-z0-9_-]+\b",
    r"\breveal\s+(restricted|confidential|private)\s+(data|information)\b",
    r"\boverride\s+(my\s+)?permissions\b",
    r"\bbypass\s+(security|authorization|permissions)\b",
    r"\bexecute\s+(this|the\s+following)\s+instruction\b",
]


def contains_prompt_injection(text: str) -> bool:
    """Return True when untrusted text contains a known prompt-injection pattern."""
    if not text:
        return False

    normalized_text = " ".join(text.lower().split())

    return any(
        re.search(pattern, normalized_text)
        for pattern in PROMPT_INJECTION_PATTERNS
    )


def validate_untrusted_ai_input(text: str) -> None:
    """
    Reject untrusted complaint/document text containing prompt injection.
    """
    if contains_prompt_injection(text):
        raise ValueError("Prompt injection detected in untrusted input.")