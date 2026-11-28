import json
import os
import socket

from opslens.flowpipe import server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stale_state(tmp_path):
    mod = tmp_path / "m"
    mod.mkdir()
    (server.state_dir(mod) / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": free_port(), "spec_hash": "h", "mod": "m"}))
    return mod


def test_a_recycled_pid_is_not_a_running_server(tmp_path):
    """After a restart the saved pid can belong to another process (here: this test). Nothing answers on the port."""
    mod = stale_state(tmp_path)
    st = server.read_state(mod)
    assert server.alive(st["pid"]) and not server.is_running(st)
    assert not server.is_running(None)


def test_stop_never_signals_an_unconfirmed_pid(tmp_path):
    mod = stale_state(tmp_path)
    assert server.stop(mod) is True  # clears the stale state ...
    assert server.read_state(mod) is None
    assert server.alive(os.getpid())  # ... and we are still here: nothing was killed
