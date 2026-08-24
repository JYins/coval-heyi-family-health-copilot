from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class ProcessRestartTest(unittest.TestCase):
    def test_approved_record_survives_backend_process_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "restart.sqlite"
            port = _free_port()
            process = _start_api(database_path, port)
            try:
                _wait_for_api(port)
                record = _request_json(
                    port,
                    "POST",
                    "/ingestions",
                    {
                        "member_id": "mom",
                        "text": "进程重启 synthetic 测试：今天咳嗽，没有胸痛。",
                        "input_mode": "text",
                        "event_date": "2026-08-19",
                        "source_label": "process restart fixture",
                        "idempotency_key": "process-ingest-0001",
                    },
                )
                approved = _request_json(
                    port,
                    "POST",
                    f"/records/{record['id']}/approve",
                    {
                        "member_id": "mom",
                        "candidate_id": record["candidate_id"],
                        "candidate_revision": record["candidate_revision"],
                        "idempotency_key": "process-approve-0001",
                    },
                )
                self.assertEqual(1, approved["version_number"])
            finally:
                _stop_api(process)

            restarted = _start_api(database_path, port)
            try:
                _wait_for_api(port)
                query = urllib.parse.urlencode({"member_id": "mom"})
                timeline = _request_json(port, "GET", f"/timeline?{query}")
                self.assertEqual(1, len(timeline))
                self.assertEqual(record["id"], timeline[0]["id"])
                self.assertEqual(1, timeline[0]["version_number"])
            finally:
                _stop_api(restarted)

    @unittest.skipUnless(
        os.environ.get("COVAL_RUN_REAL_PROVIDER_RESTART") == "1",
        "real local provider restart audit is opt-in",
    )
    def test_real_provider_provenance_survives_backend_process_restart(self) -> None:
        self.assertEqual("transformers_adapter", os.environ.get("COVAL_MODEL_PROVIDER"))
        started_at = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "real-provider-restart.sqlite"
            port = _free_port()
            process = _start_api(database_path, port)
            try:
                _wait_for_api(port)
                health = _request_json(port, "GET", "/health")
                self.assertTrue(health["model_runtime"]["network_guard"])
                record = _request_json(
                    port,
                    "POST",
                    "/ingestions",
                    {
                        "member_id": "mom",
                        "text": "真实 provider 进程重启 synthetic 测试：昨晚开始咳嗽，没有胸痛。",
                        "input_mode": "text",
                        "event_date": "2026-08-19",
                        "source_label": "real provider restart fixture",
                        "idempotency_key": "real-provider-ingest-0001",
                    },
                )
                _request_json(
                    port,
                    "POST",
                    f"/records/{record['id']}/approve",
                    {
                        "member_id": "mom",
                        "candidate_id": record["candidate_id"],
                        "candidate_revision": record["candidate_revision"],
                        "idempotency_key": "real-provider-approve-0001",
                    },
                )
            finally:
                _stop_api(process)

            restarted = _start_api(database_path, port)
            try:
                _wait_for_api(port)
                restored = _request_json(port, "GET", f"/records/{record['id']}?member_id=mom")
                extraction = restored["extraction"]
                self.assertEqual("transformers_adapter", extraction["provider"])
                self.assertIn("Qwen/Qwen2.5-7B-Instruct", extraction["model_ref"])
                self.assertIn("LoRA SFT v2", extraction["model_ref"])
                self.assertIn("bnb-4bit-nf4", extraction["model_ref"])
                self.assertEqual("sft-v2-schema-v3-template-v1", extraction["extraction_version"])
                self.assertEqual("schema_v3", extraction["prompt_version"])
                self.assertEqual("health-memory-v1", extraction["schema_version"])

                audit_path_text = os.environ.get("COVAL_REAL_PROVIDER_RESTART_AUDIT_PATH", "").strip()
                if audit_path_text:
                    audit_path = Path(audit_path_text)
                    audit_path.parent.mkdir(parents=True, exist_ok=True)
                    completed_at = datetime.now(timezone.utc)
                    audit_path.write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "synthetic_only": True,
                                "status": "PASS",
                                "started_at": started_at.isoformat(),
                                "completed_at": completed_at.isoformat(),
                                "elapsed_seconds": round((completed_at - started_at).total_seconds(), 3),
                                "process_start_count": 2,
                                "network_guard": health["model_runtime"]["network_guard"],
                                "provider": extraction["provider"],
                                "model_ref": extraction["model_ref"],
                                "extraction_version": extraction["extraction_version"],
                                "prompt_version": extraction["prompt_version"],
                                "schema_version_persisted": extraction["schema_version"],
                                "record_version": restored["version_number"],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
            finally:
                _stop_api(restarted)


def _start_api(database_path: Path, port: int) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["COVAL_HEALTH_DB_PATH"] = str(database_path)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.serve.coval_health_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_api(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_for_api(port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            _request_json(port, "GET", "/health")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.15)
    raise AssertionError("API did not become ready")


def _request_json(port: int, method: str, path: str, body: dict[str, object] | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    timeout = 180 if os.environ.get("COVAL_RUN_REAL_PROVIDER_RESTART") == "1" else 5
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


if __name__ == "__main__":
    unittest.main()
