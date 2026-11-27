"""Live planner eval against a real model (opt-in: spends tokens). Needs OPSLENS_SYSTEM=1 and an llm provider, e.g.
OPSLENS__LLM__PROVIDER=anthropic (+ ANTHROPIC_API_KEY) or openrouter/glm/openai with OPSLENS__LLM__MODEL.
Pass criteria per case: validates clean, reads the expected tables, uses the expected pipelines, and every change is gated."""

import os
from pathlib import Path

import pytest
import yaml

from opslens.ai import planner
from opslens.ai.providers import make_provider
from opslens.catalog import pipelines as pcat
from opslens.config import load_config
from opslens.sql import guard

CASES = yaml.safe_load((Path(__file__).parents[2] / "evals" / "planner_cases.yaml").read_text())
pytestmark = [pytest.mark.system,
              pytest.mark.skipif(os.environ.get("OPSLENS_SYSTEM") != "1", reason="set OPSLENS_SYSTEM=1"),
              pytest.mark.skipif(not os.environ.get("OPSLENS__LLM__PROVIDER"), reason="set OPSLENS__LLM__PROVIDER")]


@pytest.mark.parametrize("case", CASES, ids=[c["ask"][:50] for c in CASES])
def test_case(case):
    cfg, _ = load_config()
    plan = planner.plan(case["ask"], make_provider(cfg.llm), max_attempts=cfg.llm.max_attempts)
    spec = plan.spec
    tabs = guard.tables_in(spec.detect.sql, "postgres")
    for t in case["tables"]:
        assert t in tabs, (t, tabs)
    used = {a.pipeline for a in spec.actions}
    for p in case["pipelines"]:
        assert p in used, (p, used)
    for p in case["gated"]:
        assert any(a.gated for a in spec.actions if a.pipeline == p), p
    pc = pcat.load()
    for a in spec.actions:
        if pc.get(a.pipeline).effect == "change":
            assert a.gated, a.pipeline
