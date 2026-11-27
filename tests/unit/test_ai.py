import json
from types import SimpleNamespace

import httpx
import pytest

from opslens.ai import planner
from opslens.ai.providers import AnthropicProvider, LLMError, OpenAIStyle, Reply, make_provider
from opslens.config import LLMConfig

pytestmark = pytest.mark.unit

GOOD = """```yaml
name: idle_volumes
title: Unattached volumes
trigger: {kind: manual}
detect:
  sql: select volume_id, region, size from aws_ebs_volume where state = 'available'
actions:
  - pipeline: jira.create_issue
    args:
      project_key: OPS
      issue_type: Task
      summary: "Unattached {volume_id} ({size} GiB) in {region}"
  - pipeline: aws.delete_ebs_volume
    gated: true
    args: {volume_id: "{volume_id}", region: "{region}"}
```"""
BAD_TABLE = GOOD.replace("aws_ebs_volume", "aws_ebs_volumes_typo")
UNGATED = GOOD.replace("    gated: true\n", "")


class Fake:
    name, model = "fake", "fake-1"

    def __init__(self, *texts, refuse=False):
        self.texts, self.calls, self.refuse = list(texts), [], refuse

    def complete(self, system, messages):
        self.calls.append(list(messages))
        return Reply(self.texts.pop(0), self.refuse, {"input": 10, "output": 5})


def test_good_spec_first_try():
    f = Fake(GOOD)
    p = planner.plan("find unattached ebs volumes and open a jira ticket for each", f)
    assert p.attempts == 1 and p.spec.name == "idle_volumes" and p.usage == {"input": 10, "output": 5}
    assert p.spec.request.startswith("find unattached")
    assert "aws_ebs_volume" in f.calls[0][0]["content"] and "jira" in f.calls[0][0]["content"]  # grounded in the catalog


def test_validation_errors_are_fed_back_and_retried():
    f = Fake(BAD_TABLE, GOOD)
    p = planner.plan("find unattached ebs volumes and open a jira ticket", f)
    assert p.attempts == 2
    retry = f.calls[1]
    assert retry[-1]["role"] == "user" and "failed validation" in retry[-1]["content"] and "aws_ebs_volumes_typo" in retry[-1]["content"]
    assert retry[-2]["role"] == "assistant"


def test_ungated_delete_is_rejected_until_fixed():
    p = planner.plan("clean up unattached ebs volumes", Fake(UNGATED, GOOD))
    assert p.attempts == 2 and p.spec.gated_actions()


def test_gives_up_after_max_attempts():
    with pytest.raises(planner.PlannerError, match="no valid spec after 2"):
        planner.plan("clean up unattached ebs volumes", Fake(BAD_TABLE, BAD_TABLE), max_attempts=2)


def test_garbage_reply_is_feedback_not_a_crash():
    p = planner.plan("clean up unattached ebs volumes", Fake("sorry, I cannot", GOOD))
    assert p.attempts == 2


def test_model_cannot_waive_approval():
    p = planner.plan("clean up unattached ebs volumes", Fake(GOOD.replace("trigger:", "auto_apply: true\ntrigger:")))
    assert p.spec.auto_apply is False and p.spec.gated_actions()


def test_refusal_is_reported():
    with pytest.raises(planner.PlannerError, match="declined"):
        planner.plan("clean up unattached ebs volumes", Fake("", refuse=True))


def test_requirement_too_short():
    with pytest.raises(planner.PlannerError):
        planner.plan("hi", Fake())


def test_redaction_scrubs_before_sending():
    f = Fake(GOOD)
    planner.plan("volumes in 123456789012 owned by bob@example.com arn:aws:ec2:us-east-1:123456789012:volume/vol-1 "
                 "key AKIAABCDEFGHIJKLMNOP", f)
    sent = f.calls[0][0]["content"]
    for leaked in ("123456789012", "bob@example.com", "AKIAABCDEFGHIJKLMNOP", "volume/vol-1"):
        assert leaked not in sent
    assert "<account-id>" in sent and "<email>" in sent


# ---- providers


def openai_like(handler):
    return OpenAIStyle("openrouter", "https://x/v1", "m1", "KEY", transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_openai_style_request_and_parse():
    seen = {}

    def h(req):
        seen.update(url=str(req.url), auth=req.headers["authorization"], body=json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 7, "completion_tokens": 3}, "model": "m1"})
    r = openai_like(h).complete("SYS", [{"role": "user", "content": "q"}])
    assert r.text == "hi" and r.usage == {"input": 7, "output": 3} and not r.refused
    assert seen["url"] == "https://x/v1/chat/completions" and seen["auth"] == "Bearer KEY"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "SYS"} and seen["body"]["model"] == "m1"


def test_openai_style_retries_then_succeeds_and_surfaces_errors():
    n = {"i": 0}

    def flaky(req):
        n["i"] += 1
        return httpx.Response(429 if n["i"] < 3 else 200, json={"choices": [{"message": {"content": "ok"}}]})
    assert openai_like(flaky).complete("s", []).text == "ok" and n["i"] == 3
    with pytest.raises(LLMError, match="401"):
        openai_like(lambda r: httpx.Response(401, text="bad key")).complete("s", [])
    r = openai_like(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]})).complete("s", [])
    assert r.refused


def test_error_never_contains_the_key():
    with pytest.raises(LLMError) as e:
        openai_like(lambda r: httpx.Response(500, text="boom")).complete("s", [])
    assert "KEY" not in str(e.value)


@pytest.mark.parametrize("provider,url,keyvar", [
    ("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    ("glm", "https://open.bigmodel.cn/api/paas/v4", "ZAI_API_KEY"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
])
def test_presets(provider, url, keyvar):
    p = make_provider(LLMConfig(provider=provider, model="m"), {keyvar: "k"})
    assert p.base == url and p.key == "k" and p.name == provider


def test_provider_config_errors_are_actionable():
    with pytest.raises(LLMError, match="no AI provider"):
        make_provider(LLMConfig(), {})
    with pytest.raises(LLMError, match="llm.model is required"):
        make_provider(LLMConfig(provider="openai"), {"OPENAI_API_KEY": "k"})
    with pytest.raises(LLMError, match="needs an API key in \\$OPENAI_API_KEY"):
        make_provider(LLMConfig(provider="openai", model="m"), {})
    with pytest.raises(LLMError, match="base_url is required"):
        make_provider(LLMConfig(provider="openai_compatible", model="m"), {})


def test_openai_compatible_and_ollama_need_no_key():
    p = make_provider(LLMConfig(provider="openai_compatible", model="m", base_url="http://gpu:8000/v1/"), {})
    assert p.base == "http://gpu:8000/v1" and p.key is None
    assert make_provider(LLMConfig(provider="ollama", model="llama"), {}).base == "http://localhost:11434/v1"


def test_api_key_env_override():
    p = make_provider(LLMConfig(provider="openai", model="m", api_key_env="MY_KEY"), {"MY_KEY": "abc"})
    assert p.key == "abc"


class FakeAnthropic:
    def __init__(self):
        self.calls = []
        msg = SimpleNamespace(content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text="spec")],
                              stop_reason="end_turn", model="claude-opus-5-5",
                              usage=SimpleNamespace(input_tokens=4, output_tokens=2, cache_read_input_tokens=3))
        outer = self

        class M:
            def create(self, **kw):
                outer.calls.append(kw)
                return msg
        self.messages = M()
        self.beta = SimpleNamespace(messages=M())


def test_anthropic_defaults_to_opus_with_adaptive_thinking_cache_and_fallback():
    c = FakeAnthropic()
    prov = make_provider(LLMConfig(provider="anthropic"), {}) if False else AnthropicProvider("claude-opus-5-5", "high", True, c)
    r = prov.complete("SYS", [{"role": "user", "content": "q"}])
    kw = c.calls[0]
    assert r.text == "spec" and r.usage["cache_read"] == 3
    assert kw["thinking"] == {"type": "adaptive"} and kw["output_config"] == {"effort": "high"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in kw


def test_anthropic_unlisted_model_uses_plain_request():
    c = FakeAnthropic()
    AnthropicProvider("claude-haiku-4-5", "high", True, c).complete("s", [])
    assert "thinking" not in c.calls[0] and "fallbacks" not in c.calls[0]


def test_anthropic_refusal_flag():
    c = FakeAnthropic()
    c.beta.messages.create = lambda **kw: SimpleNamespace(content=[], stop_reason="refusal", model="m", usage=None)
    assert AnthropicProvider("claude-opus-5-5", "high", True, c).complete("s", []).refused
