import json

import httpx
import pytest

from opslens.flowpipe.client import Flowpipe, FlowpipeError, waiting_input_step
from opslens.runs.store import Audit

pytestmark = pytest.mark.unit


def fake(routes):
    def handler(req: httpx.Request) -> httpx.Response:
        for suffix, resp in routes.items():
            if req.url.path.endswith(suffix):
                return resp(req) if callable(resp) else httpx.Response(200, json=resp)
        return httpx.Response(404, json={"detail": f"no route {req.url.path}"})
    return Flowpipe("http://x:7103", transport=httpx.MockTransport(handler))


def exec_doc(step_status, output=None, errors=None):
    return {"pipeline_executions": {"p1": {"step_status": step_status, "pipeline_output": output or {},
                                           "errors": errors or []}}}


QUEUED = {"input.approve": {"0": {"queued": {"s1": True}, "started": {}, "finished": {}, "failed": {}}}}
DONE = {"input.approve": {"0": {"queued": {}, "started": {}, "finished": {"s1": True}, "failed": {}}}}


def test_waiting_input_step_detection():
    assert waiting_input_step(QUEUED) == "approve"
    assert waiting_input_step(DONE) is None
    assert waiting_input_step({"transform.a": QUEUED["input.approve"]}) is None  # only input steps count


def test_started_run_with_an_unanswered_input_is_waiting():
    c = fake({"/process/e1": {"status": "started"}, "/process/e1/execution": exec_doc(QUEUED),
              "/log/process.json": 'blah /form/abc123/xyz789 blah'})
    st = c.state("e1")
    assert st.status == "waiting" and st.waiting_on == "approve" and st.approval_url.endswith("/form/abc123/xyz789")


def test_started_run_without_input_is_running_and_finished_has_outputs():
    c = fake({"/process/e1": {"status": "started"}, "/process/e1/execution": exec_doc(DONE)})
    assert c.state("e1").status == "started"
    c = fake({"/process/e1": {"status": "finished"}, "/process/e1/execution": exec_doc(DONE, {"found": 8})})
    st = c.state("e1")
    assert st.status == "finished" and st.outputs == {"found": 8} and st.done


def test_a_just_started_run_is_not_an_error():
    c = fake({"/process/e1": lambda r: httpx.Response(404, json={"detail": "No pipeline found for process e1"})})
    assert c.state("e1").status == "started"


def test_failed_run_carries_the_error():
    c = fake({"/process/e1": {"status": "failed"},
              "/process/e1/execution": exec_doc({}, errors=[{"error": {"detail": "step exploded"}}])})
    assert c.state("e1").error == "step exploded"


def test_answer_posts_the_step_name_as_the_key():
    seen = {}

    def handler(req):
        seen["body"], seen["path"] = json.loads(req.content), req.url.path
        return httpx.Response(200, json={})
    Flowpipe("http://x", transport=httpx.MockTransport(handler)).answer("http://x/form/id1/h1", "approve", "approve")
    assert seen == {"body": {"approve": "approve"}, "path": "/api/latest/form/id1/h1/submit"}


def test_unreachable_server_is_a_clear_error():
    def boom(req):
        raise httpx.ConnectError("refused")
    with pytest.raises(FlowpipeError, match="cannot reach"):
        Flowpipe("http://x", transport=httpx.MockTransport(boom)).run("m.pipeline.p")
    assert Flowpipe("http://x", transport=httpx.MockTransport(boom)).up() is False


def test_wait_for_pipeline_polls_until_the_watcher_loads_it():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json={}) if calls["n"] >= 3 else httpx.Response(404, json={"detail": "nope"})
    c = Flowpipe("http://x", transport=httpx.MockTransport(handler))
    c.wait_for_pipeline("m.pipeline.p", sleep=lambda s: None)
    assert calls["n"] == 3


def test_audit_log_is_append_only_and_ordered(tmp_path):
    a = Audit(tmp_path)
    a.log("deploy", "m", "abc", "port 1", actor="alice")
    a.log("run", "m", "abc", "exec_1", actor="alice")
    ev = a.events("m")
    assert [e["kind"] for e in ev] == ["run", "deploy"] and ev[0]["actor"] == "alice"
    assert a.events("other") == []
