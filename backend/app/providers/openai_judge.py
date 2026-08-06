from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.providers.contracts import (
    JudgeOutcome,
    ProviderCallRecord,
    ProviderOutputError,
    RuntimeProviderError,
)


class _JudgeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_score: int = Field(ge=1, le=5)
    age_score: int = Field(ge=1, le=5)
    instruction_score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1, max_length=500)


class OpenAIJudgeProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.judge_model
        self._client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def _error(error: Exception) -> RuntimeProviderError:
        if isinstance(error, APITimeoutError):
            return RuntimeProviderError("JUDGE_TIMEOUT", True)
        if isinstance(error, RateLimitError):
            return RuntimeProviderError("JUDGE_RATE_LIMITED", True)
        if isinstance(error, APIStatusError) and error.status_code < 500:
            return RuntimeProviderError("JUDGE_REJECTED", False)
        return RuntimeProviderError("JUDGE_UNAVAILABLE", True)

    def judge(
        self,
        *,
        safe_case_prompt: str,
        expected_behavior: str,
        audience_age: str,
        displayed_output: str,
        evidence: list[dict[str, object]],
    ) -> JudgeOutcome:
        started = time.perf_counter()
        payload = {
            "case_prompt": safe_case_prompt,
            "expected_behavior": expected_behavior,
            "audience_age": audience_age,
            "displayed_output": displayed_output,
            "retrieved_evidence": evidence,
        }
        try:
            response = self._client.responses.parse(
                model=self._model,
                input=[
                    {
                        "role": "developer",
                        "content": (
                            "You are a strict teacher evaluator. Score only the supplied output "
                            "against supplied evidence and behavior. Evidence support, age "
                            "appropriateness, and instruction following are integers 1-5. "
                            "Unsupported claims lower evidence. Return a short rationale."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                text_format=_JudgeSchema,
                max_output_tokens=220,
            )
        except (APITimeoutError, RateLimitError, APIConnectionError, APIStatusError) as error:
            raise self._error(error) from error
        parsed = response.output_parsed
        if parsed is None:
            raise ProviderOutputError
        usage = response.usage
        call = ProviderCallRecord(
            operation="TEACHER_JUDGE",
            model=self._model,
            input_tokens=int(usage.input_tokens if usage else 0),
            output_tokens=int(usage.output_tokens if usage else 0),
            reasoning_tokens=0,
            latency_ms=round((time.perf_counter() - started) * 1000),
            timestamp=datetime.now(UTC).isoformat(),
        )
        return JudgeOutcome(
            evidence_score=parsed.evidence_score,
            age_score=parsed.age_score,
            instruction_score=parsed.instruction_score,
            rationale=parsed.rationale.strip(),
            call=call,
        )
