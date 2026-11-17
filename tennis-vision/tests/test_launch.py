import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import launch


def make_copy(parent, name, jobs=(), with_launcher=True):
    """An unzipped copy of the app with some saved videos in it."""
    folder = parent / name
    (folder / "data" / "jobs").mkdir(parents=True)
    if with_launcher:
        (folder / "launch.py").write_text("# launcher")
    for job_id in jobs:
        job = folder / "data" / "jobs" / job_id
        job.mkdir()
        (job / "job.json").write_text(json.dumps(dict(id=job_id)))
        (job / "report.json").write_text("{}")
    return folder


def test_pytorch_is_installed_on_its_own():
    lines = launch.requirement_lines()
    assert "mediapipe" in lines and "fpdf2" in lines and not any(l.lower().startswith("torch") for l in lines)
    assert all("#" not in l for l in lines)


@pytest.mark.parametrize("system, env, want", [
    ("Windows", {"LOCALAPPDATA": "C:/Users/T/AppData/Local"}, "C:/Users/T/AppData/Local/TracerTennis"),
    ("Darwin", {}, "~/Library/Application Support/Tracer Tennis"),
    ("Linux", {}, "~/.local/share/tracer-tennis"),
])
def test_one_folder_per_computer(monkeypatch, system, env, want):
    monkeypatch.setattr(launch.platform, "system", lambda: system)
    monkeypatch.delenv("TRACER_TENNIS_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert launch.app_home().as_posix() == launch.Path(want).expanduser().as_posix()
    monkeypatch.setenv("TRACER_TENNIS_HOME", "/somewhere/else")
    assert launch.app_home().as_posix() == "/somewhere/else"


def test_saved_videos_come_over_from_older_copies_once(tmp_path, monkeypatch):
    old = make_copy(tmp_path, "tracer-tennis", ["aaaaaaaaaaa1", "aaaaaaaaaaa2"])
    new = make_copy(tmp_path, "tracer-tennis (2)", ["aaaaaaaaaaa3"])
    make_copy(tmp_path, "holiday photos", ["bbbbbbbbbbb1"], with_launcher=False)          # not a copy of the app
    home = tmp_path / "home"
    (home / "data" / "jobs" / "aaaaaaaaaaa2").mkdir(parents=True)                         # already there: kept as is
    monkeypatch.setattr(launch, "ROOT", new)
    assert launch.bring_over_saved_videos(home) == 2
    assert sorted(p.name for p in (home / "data" / "jobs").iterdir()) == ["aaaaaaaaaaa1", "aaaaaaaaaaa2", "aaaaaaaaaaa3"]
    assert (old / "data" / "jobs" / "aaaaaaaaaaa1" / "report.json").exists()                # the old copy is left alone
    assert (old / "data" / "jobs" / launch.MOVED).exists() and (new / "data" / "jobs" / launch.MOVED).exists()
    assert not (home / "data" / "jobs" / "aaaaaaaaaaa2" / "job.json").exists()
    # a video deleted in the app later must not come back from the old copy
    import shutil
    shutil.rmtree(home / "data" / "jobs" / "aaaaaaaaaaa1")
    assert launch.bring_over_saved_videos(home) == 0 and not (home / "data" / "jobs" / "aaaaaaaaaaa1").exists()


def test_a_second_double_click_opens_the_running_app(monkeypatch):
    class Info(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(dict(computer="pc", urls=[])).encode())

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Info)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(launch, "PORTS", [port])
        assert launch.pick_port() == (port, True)
    finally:
        server.shutdown()
    busy = socket.socket()
    busy.bind(("0.0.0.0", 0))
    busy.listen()
    taken = busy.getsockname()[1]
    try:
        monkeypatch.setattr(launch, "PORTS", [taken, taken + 1])
        assert launch.pick_port() == (taken + 1, False)                 # something else on the first port: use the next
    finally:
        busy.close()


def test_an_unsupported_python_hands_over_to_a_supported_one(monkeypatch):
    calls = []
    monkeypatch.setattr(launch.sys, "version_info", (3, 15, 0))
    monkeypatch.setattr(launch.platform, "system", lambda: "Windows")
    monkeypatch.setattr(launch, "probe", lambda cmd: ((3, 12), "C:/Py312/python.exe", "AMD64") if cmd == ["py", "-3.12"] else None)
    monkeypatch.setattr(launch.subprocess, "call", lambda cmd, **k: calls.append(cmd) or 0)
    with pytest.raises(SystemExit) as done:
        launch.ensure_supported_python()
    assert done.value.code == 0 and calls[0][0] == "C:/Py312/python.exe" and calls[0][1].endswith("launch.py")


def test_no_supported_python_says_what_to_install(monkeypatch):
    monkeypatch.setattr(launch.sys, "version_info", (3, 15, 0))
    monkeypatch.setattr(launch.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(launch.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(launch, "probe", lambda cmd: None)
    with pytest.raises(SystemExit) as done:
        launch.ensure_supported_python()
    assert "3.12 or 3.13 or 3.14" in str(done.value.code) and "universal2" in str(done.value.code)


def test_supported_versions():
    assert [launch.supported(v) for v in [(3, 11), (3, 12), (3, 13), (3, 14), (3, 15)]] == [False, True, True, True, False]
    assert launch.supported(sys.version_info[:2]), "the Python running the tests should be one the app supports"


def test_the_port_used_last_time_comes_first_and_survives_a_quick_restart(monkeypatch):
    """The iPhone icon remembers the address, port included, so a restart must land on the same port."""
    import socket as so
    probe = so.socket()
    probe.bind(("0.0.0.0", 0))
    port = probe.getsockname()[1]
    probe.close()
    monkeypatch.setattr(launch, "PORTS", range(port - 3, port + 3))
    assert launch.pick_port(port) == (port, False)
    # a server that just closed leaves its port in TIME_WAIT: it must still count as free
    srv = so.socket()
    srv.setsockopt(so.SOL_SOCKET, so.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen()
    cli = so.create_connection(("127.0.0.1", port))
    conn, _ = srv.accept()
    conn.close()          # the server side closes first, so its end of the connection waits in TIME_WAIT
    cli.close()
    srv.close()
    assert launch.pick_port(port) == (port, False)
