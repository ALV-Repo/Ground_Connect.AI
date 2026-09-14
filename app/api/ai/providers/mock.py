from typing import Dict

from app.api.ai.providers.base import AIProvider


class MockAIProvider(AIProvider):
    """
    Deterministic AI provider for development and testing.

    No external API key is required.
    """

    def summarize(
        self,
        text: str,
        content_type: str = "general",
    ) -> str:

        text = text.strip()

        if not text:
            return ""

        # Short text does not need further reduction.
        if len(text) <= 200:
            return text

        # Basic deterministic sentence extraction.
        sentences = [
            sentence.strip()
            for sentence in text.replace("!", ".").replace("?", ".").split(".")
            if sentence.strip()
        ]

        if len(sentences) <= 2:
            return text[:200] + "..."

        summary = ". ".join(sentences[:2])

        if not summary.endswith("."):
            summary += "."

        return summary

    def translate(
        self,
        text: str,
        target_language: str,
    ) -> str:

        target_language = target_language.lower().strip()

        translations: Dict[str, Dict[str, str]] = {
            "hindi": {
                "hello": "नमस्ते",
                "good morning": "सुप्रभात",
                "good evening": "शुभ संध्या",
                "thank you": "धन्यवाद",
                "welcome": "स्वागत है",
                "yes": "हाँ",
                "no": "नहीं",
            },
            "english": {
                "नमस्ते": "Hello",
                "सुप्रभात": "Good morning",
                "शुभ संध्या": "Good evening",
                "धन्यवाद": "Thank you",
                "स्वागत है": "Welcome",
                "हाँ": "Yes",
                "नहीं": "No",
            },
            "kannada": {
                "hello": "ನಮಸ್ಕಾರ",
                "good morning": "ಶುಭೋದಯ",
                "good evening": "ಶುಭ ಸಂಜೆ",
                "thank you": "ಧನ್ಯವಾದಗಳು",
                "welcome": "ಸ್ವಾಗತ",
                "yes": "ಹೌದು",
                "no": "ಇಲ್ಲ",
            },
        }

        result = text

        language_dictionary = translations.get(
            target_language,
            {},
        )

        for source, translated in language_dictionary.items():
            result = result.replace(source, translated)

        return result

    def transcribe(
        self,
        filename: str,
        language: str | None = None,
    ) -> dict:

        detected_language = language or "hi-IN"

        return {
            "transcript": (
                f"Mock transcription generated for {filename}"
            ),
            "language": detected_language,
            "confidence": 0.92,
            "speaker_confirmed": False,
            "committed": False,
        }


mock_provider = MockAIProvider()