import io

import pytest
from fastapi.testclient import TestClient

import app.server as server


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    monkeypatch.setattr(server, "jobs", {})
    submitted = []
    monkeypatch.setattr(server.worker, "submit", lambda fn, job_id: submitted.append(job_id))
    c = TestClient(server.app)
    c.submitted = submitted
    return c


def upload(client, **fields):
    return client.post("/api/jobs", files={"video": ("clip.MOV", io.BytesIO(b"not really a video"), "video/quicktime")}, data=fields)


def test_upload_queues_a_job_and_stores_options(client):
    r = upload(client, kind="match", format="doubles", names="Dani, Pat ,X,Y", height_cm="168",
               corners="[[0.3,0.3],[0.7,0.3],[0.8,0.8],[0.2,0.8]]")
    assert r.status_code == 200
    job_id = r.json()["id"]
    assert client.submitted == [job_id]
    job = server.jobs[job_id]
    assert job["params"]["names"] == ["Dani", "Pat", "X", "Y"] and job["params"]["format"] == "doubles"
    assert job["params"]["corners"][2] == [0.8, 0.8] and abs(job["params"]["height_m"] - 1.68) < 1e-9
    assert job["video"] == "source.mov"
    listed = client.get("/api/jobs").json()
    assert listed[0]["id"] == job_id and listed[0]["status"] == "queued"


@pytest.mark.parametrize("fields", [
    dict(kind="other"), dict(kind="match", format="triples"), dict(hand="both"), dict(height_cm="20"),
    dict(kind="match", corners="[[0.1,0.1]]"), dict(kind="match", corners="[[0,0],[1,0],[1,1],[0,2]]"), dict(kind="match", corners="oops"),
])
def test_bad_options_are_rejected(client, fields):
    assert upload(client, **fields).status_code == 400
    assert client.submitted == []


def test_files_cannot_escape_the_job_folder(client):
    job_id = upload(client).json()["id"]
    (server.DATA / job_id / "report.json").write_text("{}")
    assert client.get(f"/files/{job_id}/report.json").status_code == 200
    assert client.get(f"/files/{job_id}/source.mov").status_code == 404        # the raw upload is not served back
    assert client.get(f"/files/{job_id}/job.json").status_code == 404
    assert client.get(f"/files/{job_id}/..%2F..%2Fserver.py").status_code == 404
    assert client.get("/files/not-a-job/report.json").status_code == 404
    assert client.get("/api/jobs/0123456789ab").status_code == 404


def test_phone_access_info_qr_and_home_screen_files(client, monkeypatch):
    monkeypatch.setattr(server, "lan_addresses", lambda: ["192.168.1.23"])
    monkeypatch.setattr(server, "PORT", 8000)
    assert client.get("/api/info").json()["urls"] == ["http://192.168.1.23:8000"]
    qr = client.get("/api/qr")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg") and b"<svg" in qr.content
    manifest = client.get("/static/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and manifest["start_url"] == "/"
    for icon in manifest["icons"] + [{"src": "/static/icon-180.png"}]:
        assert client.get(icon["src"]).status_code == 200
    page = client.get("/").text
    assert 'rel="manifest"' in page and 'rel="apple-touch-icon"' in page
    monkeypatch.setattr(server, "lan_addresses", lambda: [])
    assert client.get("/api/qr").status_code == 404


def finished_swing_job(tmp_path, job_id, kind="swing", contact_cm=2, status="work"):
    """A done job on disk with a one-swing report, as the pipeline leaves it."""
    from tennisvision.swing.coach import coach
    metrics = [dict(key="contact_in_front", label="Contact in front of the body", value=contact_cm, unit="cm", phase="Contact",
                    typical="20-45", status=status, note="")]
    swing = dict(index=1, stroke="forehand", hand="right", times=dict(contact=1.5), frames=dict(contact=45), metrics=metrics,
                 coaching=coach([type("M", (), m)() for m in metrics], "forehand"), serve=None)
    folder = tmp_path / job_id
    folder.mkdir()
    (folder / "report.json").write_text(server.json.dumps(dict(
        kind="swing", video=dict(fps=30.0), swings=[swing], keyframes={"1:contact": "swing1_contact.jpg"},
        files=dict(overlay="overlay.mp4", clean="clean.mp4", tracks="tracks.json"))))
    server.jobs[job_id] = dict(id=job_id, kind=kind, status="done", created=float(int(job_id[-1], 16)), title=f"Clip {job_id[-1]}", params={})


def test_serve_jobs_carry_the_serve_type(client):
    job_id = upload(client, kind="serve", serve_type="kick").json()["id"]
    assert server.jobs[job_id]["kind"] == "serve" and server.jobs[job_id]["params"]["serve_type"] == "kick"
    assert upload(client, kind="serve", serve_type="cannonball").status_code == 400


def test_swings_can_be_listed_and_compared(client, tmp_path):
    finished_swing_job(tmp_path, "0" * 11 + "1")
    finished_swing_job(tmp_path, "0" * 11 + "2", contact_cm=30, status="good")
    finished_swing_job(tmp_path, "0" * 11 + "3", kind="serve")
    rows = client.get("/api/swings").json()
    assert [r["ref"] for r in rows] == ["0" * 11 + "3:1", "0" * 11 + "2:1", "0" * 11 + "1:1"]
    assert rows[1]["name"] == "Forehand" and rows[1]["keyframe"] == "swing1_contact.jpg" and rows[2]["counts"]["priority"] == 1
    r = client.get("/api/compare", params=dict(a=rows[2]["ref"], b=rows[1]["ref"]))
    assert r.status_code == 200
    out = r.json()
    assert out["a"]["title"] == "Clip 1" and out["b"]["contact"] == 1.5 and out["b"]["files"]["clean"] == "clean.mp4"
    assert out["worked_on"][0]["key"] == "contact_in_front" and out["worked_on"][0]["verdict"] == "better" and out["moved_right"] == 1
    assert client.get("/api/compare", params=dict(a=rows[2]["ref"], b=rows[2]["ref"])).status_code == 400
    assert client.get("/api/compare", params=dict(a=rows[2]["ref"], b=rows[0]["ref"])).status_code == 400      # swing against serve
    assert client.get("/api/compare", params=dict(a=rows[2]["ref"], b="0" * 11 + "2:9")).status_code == 404
    assert client.get("/api/compare", params=dict(a="nope:1", b=rows[1]["ref"])).status_code == 404


def test_a_video_can_be_renamed_starred_and_given_notes(client, tmp_path):
    finished_swing_job(tmp_path, "0" * 11 + "1")
    job_id = "0" * 11 + "1"
    r = client.patch(f"/api/jobs/{job_id}", json=dict(title="  Dani forehand, Tuesday  ", starred=True, notes="Work on the finish."))
    assert r.status_code == 200 and r.json()["title"] == "Dani forehand, Tuesday" and r.json()["starred"] is True
    got = client.get(f"/api/jobs/{job_id}").json()
    assert got["notes"] == "Work on the finish." and got["starred"] is True and got["marks"] == []
    assert client.get("/api/jobs").json()[0]["starred"] is True
    assert server.json.loads((tmp_path / job_id / "job.json").read_text())["notes"] == "Work on the finish."      # kept on disk
    assert client.patch(f"/api/jobs/{job_id}", json=dict(title="   ")).status_code == 400
    assert client.patch("/api/jobs/" + "f" * 12, json=dict(starred=True)).status_code == 404


def test_drawings_are_saved_with_the_video(client, tmp_path):
    finished_swing_job(tmp_path, "0" * 11 + "1")
    job_id = "0" * 11 + "1"
    marks = [[dict(tool="line", color="#ffd60a", pts=[[0.1, 0.2], [0.5, 0.61234567]]), dict(tool="angle", color="#ffffff", pts=[[0.2, 0.2], [0.3, 0.3], [0.4, 0.2]])]]
    assert client.put(f"/api/jobs/{job_id}/marks", json=marks).json() == dict(saved=2)
    back = client.get(f"/api/jobs/{job_id}").json()["marks"]
    assert back[0][0] == dict(tool="line", color="#ffd60a", pts=[[0.1, 0.2], [0.5, 0.6123]]) and back[0][1]["tool"] == "angle"
    for bad in ([[dict(tool="stamp", color="#ffffff", pts=[[0, 0], [1, 1]])]], [[dict(tool="line", color="red", pts=[[0, 0], [1, 1]])]],
                [[dict(tool="line", color="#ffffff", pts=[[0, 0]])]], [[], [], []]):
        assert client.put(f"/api/jobs/{job_id}/marks", json=bad).status_code == 400


def test_report_pdf_and_numbers_download(client, tmp_path):
    finished_swing_job(tmp_path, "0" * 11 + "1")
    job_id = "0" * 11 + "1"
    report = server.json.loads((tmp_path / job_id / "report.json").read_text())
    report["swings"][0].update(phases=[["takeback", "Ready"], ["contact", "Contact"]], two_handed=False)
    (tmp_path / job_id / "report.json").write_text(server.json.dumps(report))
    client.patch(f"/api/jobs/{job_id}", json=dict(title="Dani: forehand/1.MOV", notes="Keep the head still."))
    r = client.get(f"/api/jobs/{job_id}/report.pdf")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and len(r.content) > 1500
    assert r.headers["content-disposition"] == 'attachment; filename="Dani forehand1 report.pdf"'
    r = client.get(f"/api/jobs/{job_id}/numbers.csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("Part of the swing,Number,Value") and "Contact in front of the body,2,cm,20-45,Priority,seen directly" in lines[1]
    assert client.get(f"/api/jobs/{job_id}/report.pdf", params=dict(swing=7)).status_code == 404
    assert client.get(f"/api/jobs/{job_id}/shots.csv").status_code == 404
