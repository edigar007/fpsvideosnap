import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT_DIR / "src" / "tools"
RUNTIME_ASSET_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def test_static_runtime_assets_do_not_reference_external_urls() -> None:
    scanned_files = []
    offenders = []

    for path in STATIC_ROOT.glob("*/static/**/*"):
        if path.suffix.lower() not in {".html", ".css", ".js"}:
            continue

        scanned_files.append(path)
        text = path.read_text(encoding="utf-8")
        if RUNTIME_ASSET_PATTERN.search(text):
            offenders.append(path.relative_to(ROOT_DIR).as_posix())

    assert scanned_files, "No static runtime assets were scanned"
    assert offenders == []
