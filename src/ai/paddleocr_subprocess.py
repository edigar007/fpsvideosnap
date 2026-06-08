import atexit
import json
import os
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger("paddleocr_subprocess")


@dataclass
class PaddleOCRSubprocessConfig:
    python_exe: Path
    worker_script: Path
    cwd: Path
    startup_timeout_s: float = 60.0
    request_timeout_s: float = 30.0


class PaddleOCRSubprocess:
    """在独立 Python 进程中运行 PaddleOCR（用于规避 Windows 下 Torch↔Paddle GPU DLL 冲突）。"""

    def __init__(self, cfg: PaddleOCRSubprocessConfig):
        self._cfg = cfg
        self._proc: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._pending: Dict[str, Queue] = {}
        self._lock = threading.Lock()
        self._ready_event = threading.Event()

        atexit.register(self.close)

    @property
    def cfg(self) -> PaddleOCRSubprocessConfig:
        return self._cfg

    @staticmethod
    def default() -> "PaddleOCRSubprocessConfig":
        repo_root = Path(__file__).resolve().parents[2]
        python_exe = repo_root / ".venv_paddle" / "Scripts" / "python.exe"
        worker_script = repo_root / "scripts" / "paddleocr_worker.py"
        return PaddleOCRSubprocessConfig(
            python_exe=python_exe,
            worker_script=worker_script,
            cwd=repo_root,
        )

    def start(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return

            self._ready_event.clear()

            env = os.environ.copy()
            env.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
            env.setdefault("PYTHONUTF8", "1")

            cmd = [
                str(self._cfg.python_exe),
                "-u",
                str(self._cfg.worker_script),
            ]

            logger.info(f"Starting PaddleOCR worker: {cmd}")

            self._proc = subprocess.Popen(
                cmd,
                cwd=str(self._cfg.cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )

            assert self._proc.stdin and self._proc.stdout and self._proc.stderr

            self._reader_thread = threading.Thread(target=self._stdout_loop, daemon=True)
            self._reader_thread.start()

            self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
            self._stderr_thread.start()

        if not self._ready_event.wait(timeout=self._cfg.startup_timeout_s):
            raise TimeoutError("PaddleOCR worker did not become ready in time")

    def _stderr_loop(self) -> None:
        assert self._proc and self._proc.stderr
        for line in self._proc.stderr:
            line = line.rstrip("\n")
            if line:
                logger.debug(f"[worker stderr] {line}")

    def _stdout_loop(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(f"Unparseable worker line: {line} ({exc})")
                continue

            if msg.get("type") == "ready":
                self._ready_event.set()
                continue

            req_id = msg.get("id")
            if not req_id:
                logger.warning(f"Worker message without id: {msg}")
                continue

            with self._lock:
                q = self._pending.get(req_id)

            if q is None:
                logger.warning(f"No pending request for id={req_id}: {msg}")
                continue

            q.put(msg)

        # stdout loop ended => process likely exited
        self._ready_event.clear()

    def request(self, payload: Dict[str, Any], timeout_s: Optional[float] = None) -> Dict[str, Any]:
        self.start()

        req_id = payload.get("id") or uuid.uuid4().hex
        payload["id"] = req_id

        q: Queue = Queue(maxsize=1)
        with self._lock:
            self._pending[req_id] = q

        try:
            assert self._proc and self._proc.stdin
            self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()

            msg = q.get(timeout=timeout_s or self._cfg.request_timeout_s)
            return msg
        except Empty as exc:
            raise TimeoutError(
                f"PaddleOCR worker request timeout: {payload.get('cmd')}"
            ) from exc
        finally:
            with self._lock:
                self._pending.pop(req_id, None)

    def predict_path(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        lang: str = "ch",
        device: str = "gpu:0",
        timeout_s: Optional[float] = None,
    ) -> list:
        resp = self.request(
            {
                "cmd": "predict_path",
                "image_path": image_path,
                "offset": [offset_x, offset_y],
                "lang": lang,
                "device": device,
            },
            timeout_s=timeout_s,
        )

        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "worker error")

        return resp.get("detections", [])

    def close(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
            self._pending.clear()

        if not proc:
            return

        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as exc:
            logger.debug(f"Failed to close PaddleOCR subprocess cleanly: {exc}")
