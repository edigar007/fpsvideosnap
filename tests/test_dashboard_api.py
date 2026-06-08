from src.tools.dashboard.server import create_app


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_scan_requires_directory():
    client = _client()

    rv = client.post("/api/scan", json={"directory": ""})

    assert rv.status_code == 400


def test_scan_missing_path_returns_404(tmp_path):
    client = _client()

    rv = client.post("/api/scan", json={"directory": str(tmp_path / "missing")})

    assert rv.status_code == 404


def test_scan_file_path_returns_400(tmp_path):
    client = _client()
    file_path = tmp_path / "not_a_dir.mp4"
    file_path.write_bytes(b"video")

    rv = client.post("/api/scan", json={"directory": str(file_path)})

    assert rv.status_code == 400


def test_scan_returns_only_video_extensions(tmp_path):
    client = _client()
    (tmp_path / "clip.mp4").write_bytes(b"video")
    (tmp_path / "movie.MKV").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("skip", encoding="utf-8")

    rv = client.post("/api/scan", json={"directory": str(tmp_path)})

    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 2
    assert [video["name"] for video in data["videos"]] == ["clip.mp4", "movie.MKV"]
