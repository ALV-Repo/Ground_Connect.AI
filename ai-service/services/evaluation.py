from dataclasses import dataclass

from models.ai import CopilotResponse


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    checks: dict[str, bool]
    score: float


class AIQualityEvaluator:
    """
    Evaluates the structural quality and safety
    of a GroundConnect AI response.
    """

    def evaluate(
        self,
        response: CopilotResponse,
    ) -> EvaluationResult:

        checks = {
            "answer_present": self._answer_present(response),
            "coverage_present": self._coverage_present(response),
            "freshness_present": self._freshness_present(response),
            "facts_present": self._facts_present(response),
            "inferences_present": self._inferences_present(response),
            "recommendations_present": (
                self._recommendations_present(response)
            ),
            "prompt_injection_safe": (
                self._prompt_injection_safe(response)
            ),
        }

        passed_checks = sum(
            1
            for result in checks.values()
            if result
        )

        total_checks = len(checks)

        score = (
            passed_checks / total_checks
            if total_checks
            else 0.0
        )

        return EvaluationResult(
            passed=all(checks.values()),
            checks=checks,
            score=score,
        )

    @staticmethod
    def _answer_present(
        response: CopilotResponse,
    ) -> bool:

        return bool(response.answer.strip())

    @staticmethod
    def _coverage_present(
        response: CopilotResponse,
    ) -> bool:

        return bool(response.coverage.strip())

    @staticmethod
    def _freshness_present(
        response: CopilotResponse,
    ) -> bool:

        return bool(response.freshness.strip())

    @staticmethod
    def _facts_present(
        response: CopilotResponse,
    ) -> bool:

        return isinstance(response.facts, list)

    @staticmethod
    def _inferences_present(
        response: CopilotResponse,
    ) -> bool:

        return isinstance(response.inferences, list)

    @staticmethod
    def _recommendations_present(
        response: CopilotResponse,
    ) -> bool:

        return isinstance(response.recommendations, list)

    @staticmethod
    def _prompt_injection_safe(
        response: CopilotResponse,
    ) -> bool:

        return not response.prompt_injection_detected