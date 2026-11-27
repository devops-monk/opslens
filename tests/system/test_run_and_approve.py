"""The run/approval machinery against a real Flowpipe server (no cloud, no network): start, run, detect the wait,
answer it, finish. Pins the behaviour opslens relies on (a waiting run reports `started`; the form key is the step name)."""

import os
import shutil

import pytest

from opslens.flowpipe import server
from opslens.flowpipe.client import Flowpipe

pytestmark = [pytest.mark.system,
              pytest.mark.skipif(os.environ.get("OPSLENS_SYSTEM") != "1", reason="set OPSLENS_SYSTEM=1"),
              pytest.mark.skipif(shutil.which("flowpipe") is None, reason="flowpipe not installed")]
FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "mods", "approve")


@pytest.fixture
def served(tmp_path):
    mod = tmp_path / "approve"
    shutil.copytree(FIXTURE, mod)
    st = server.start(mod, "hash0")
    client = Flowpipe(f"http://localhost:{st['port']}")
    yield client
    server.stop(mod)


def test_run_waits_for_approval_then_finishes(served):
    served.wait_for_pipeline("appr.pipeline.approve", timeout_s=60)
    eid = served.run("appr.pipeline.approve")
    st = served.wait(eid, timeout_s=60)
    assert st.status == "waiting" and st.waiting_on == "ok" and "/form/" in st.approval_url
    served.answer(st.approval_url, st.waiting_on, "yes")
    done = served.wait(eid, timeout_s=60, until_waiting=False)
    assert done.status == "finished" and done.outputs == {"done": "ok"}
