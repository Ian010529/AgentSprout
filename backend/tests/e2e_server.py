"""Provider-boundary test server used only by local browser automation."""

from __future__ import annotations

import re
import time

from app.core.config import get_settings
from app.main import create_app
from app.providers.contracts import (
    GenerationOutcome,
    IntentOutcome,
    JudgeOutcome,
    ModerationOutcome,
    ProviderCallRecord,
)


class BrowserTestEmbeddingProvider:
    model = "text-embedding-3-small"

    def embed(self, texts: list[str]) -> list[list[float]]:
        topics = (
            ("climate", "current", "currents", "heat", "weather"),
            ("carbon", "methane"),
            ("hydrothermal", "vent", "vents", "chemosynthesis"),
            (
                "exploration",
                "explore",
                "explored",
                "tool",
                "tools",
                "satellite",
                "satellites",
                "submersible",
                "scientist",
                "scientists",
            ),
            ("acidification", "acidic"),
            ("conveyor", "circulation", "density"),
        )
        vectors: list[list[float]] = []
        for text in texts:
            tokens = re.findall(r"[a-z]+", text.lower())
            counts = [float(sum(tokens.count(term) for term in topic)) for topic in topics]
            lowered = text.lower()
            unsupported_query = any(
                marker in lowered
                for marker in ("french revolution", "quantum computers", "moons does mars")
            )
            vectors.append(
                ([0.0] * len(topics) + [1.0])
                if unsupported_query
                else [count + 0.001 for count in counts] + [0.0]
            )
        return vectors


class BrowserTestChatProvider:
    online_model = "gpt-4o-mini-2024-07-18"
    moderation_model = "omni-moderation-latest"

    @staticmethod
    def record(operation: str, model: str) -> ProviderCallRecord:
        return ProviderCallRecord(
            operation=operation,
            model=model,
            input_tokens=24 if operation in {"INTENT_CLASSIFICATION", "GENERATION"} else 0,
            output_tokens=12 if operation in {"INTENT_CLASSIFICATION", "GENERATION"} else 0,
            reasoning_tokens=0,
            latency_ms=25,
            timestamp="2026-08-06T00:00:00+00:00",
        )

    def moderate(self, text: str, operation: str) -> ModerationOutcome:
        time.sleep(0.12)
        flagged = operation == "INPUT_MODERATION" and "graphic violence" in text.lower()
        return ModerationOutcome(
            flagged=flagged,
            categories=("violence",) if flagged else (),
            call=self.record(operation, self.moderation_model),
        )

    def classify(self, message: str) -> IntentOutcome:
        time.sleep(0.12)
        lowered = message.lower()
        intent = (
            "INJECTION"
            if "hidden instructions" in lowered
            or "ignore your rules" in lowered
            or "ignore safety" in lowered
            else "HOMEWORK"
            if "final homework" in lowered or "final report" in lowered
            else "KNOWLEDGE"
        )
        return IntentOutcome(
            intent=intent,
            call=self.record("INTENT_CLASSIFICATION", self.online_model),
        )

    def generate(
        self,
        *,
        message: str,
        evidence: list[dict[str, object]],
        audience_age: str,
        tone: str,
        response_length: str,
        custom_instructions: str,
        homework: bool,
    ) -> GenerationOutcome:
        time.sleep(0.12)
        del message, audience_age, tone, response_length, custom_instructions
        answer = (
            "Start by identifying where warm and cool currents move. Then connect that heat "
            "movement to nearby weather. What pattern can you explain in your own words?"
            if homework
            else "Ocean currents move heat around Earth, influencing regional climate and "
            "weather patterns."
        )
        return GenerationOutcome(
            answer=answer,
            cited_chunk_ids=tuple(str(item["chunk_id"]) for item in evidence),
            call=self.record("GENERATION", self.online_model),
        )


class BrowserTestJudgeProvider:
    model = "gpt-4.1-mini-2025-04-14"

    def judge(
        self,
        *,
        safe_case_prompt: str,
        expected_behavior: str,
        audience_age: str,
        displayed_output: str,
        evidence: list[dict[str, object]],
    ) -> JudgeOutcome:
        del safe_case_prompt, expected_behavior, audience_age, displayed_output, evidence
        time.sleep(0.12)
        return JudgeOutcome(
            evidence_score=5,
            age_score=5,
            instruction_score=5,
            rationale="The displayed behavior follows the fixed expectation and evidence.",
            call=BrowserTestChatProvider.record("TEACHER_JUDGE", self.model),
        )


application = create_app(
    get_settings(),
    embedding_provider=BrowserTestEmbeddingProvider(),
    chat_provider=BrowserTestChatProvider(),
    judge_provider=BrowserTestJudgeProvider(),
)
