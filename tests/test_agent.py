import json

import httpx
import pytest

from api.app.agent import (
    FixtureProvider,
    GeminiProvider,
    ProviderError,
    make_provider,
    qualify_lead,
)
from api.app.config import Settings
from api.app.schemas import LeadCreate, Qualification
from api.app.seed import seed_demo
from tests.conftest import VALID_LEAD


def lead(**overrides) -> LeadCreate:
    return LeadCreate(**{**VALID_LEAD, **overrides})


def test_fixture_is_deterministic_and_valid():
    first = qualify_lead(lead(), FixtureProvider())
    second = qualify_lead(lead(), FixtureProvider())
    assert first == second
    assert first.tier == "hot" and first.score == 90


@pytest.mark.parametrize(
    ("budget", "message", "tier"),
    [("0", "hello", "cold"), ("1000", "hello", "warm"), ("5000", "hello", "hot")],
)
def test_fixture_tiers(budget, message, tier):
    assert qualify_lead(lead(budget=budget, message=message), FixtureProvider()).tier == tier


class FlakyProvider:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def generate(self, _lead):
        self.calls += 1
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


def test_invalid_output_is_retried_once_then_succeeds():
    good = Qualification(
        tier="warm", score=50, reasons=["ok"], suggested_reply="hi"
    ).model_dump_json()
    provider = FlakyProvider(["not json", good])
    assert qualify_lead(lead(), provider).score == 50
    assert provider.calls == 2


def test_inconsistent_tier_is_rejected_then_fallback():
    bad = json.dumps({"tier": "hot", "score": 10, "reasons": ["x"], "suggested_reply": "y"})
    provider = FlakyProvider([bad, bad])
    result = qualify_lead(lead(), provider)
    assert provider.calls == 2
    assert result.tier == "cold" and result.score == 0
    assert "manual review" in result.reasons[0]


def test_provider_error_falls_back_without_crashing():
    provider = FlakyProvider([ProviderError("boom"), ProviderError("boom")])
    assert qualify_lead(lead(), provider).tier == "cold"


def test_make_provider_defaults_to_fixture_and_rejects_unknown():
    assert isinstance(make_provider(Settings(database_url="sqlite://")), FixtureProvider)
    with pytest.raises(ValueError):
        make_provider(Settings(database_url="sqlite://", llm_provider="other"))


def test_gemini_requires_explicit_confirmation_and_key():
    with pytest.raises(ValueError):
        GeminiProvider("key", "gemini-model")
    with pytest.raises(ValueError):
        GeminiProvider("", "gemini-model", free_tier_confirmed=True)


def test_gemini_parses_response_with_mock_transport():
    answer = Qualification(
        tier="hot", score=80, reasons=["r"], suggested_reply="s"
    ).model_dump_json()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        body = {"candidates": [{"content": {"parts": [{"text": answer}]}}]}
        return httpx.Response(200, json=body)

    provider = GeminiProvider(
        "test-key", "gemini-model", free_tier_confirmed=True,
        transport=httpx.MockTransport(handler),
    )
    assert qualify_lead(lead(), provider).score == 80


def test_gemini_http_error_becomes_fallback():
    provider = GeminiProvider(
        "test-key", "gemini-model", free_tier_confirmed=True,
        transport=httpx.MockTransport(lambda _r: httpx.Response(500)),
    )
    assert qualify_lead(lead(), provider).tier == "cold"


def test_seed_is_idempotent_and_labeled(session_factory):
    with session_factory() as session:
        assert seed_demo(session) == 10
        assert seed_demo(session) == 0
