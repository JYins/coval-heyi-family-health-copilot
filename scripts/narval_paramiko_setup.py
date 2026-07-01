from __future__ import annotations

import argparse
import getpass
import io
import os
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import paramiko
from paramiko.ssh_exception import AuthenticationException, PartialAuthentication


SAFE_ITEMS = [
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    ".env.example",
    ".gitignore",
    "requirements-narval.txt",
    "configs",
    "data/dataset_manifest.json",
    "data/public",
    "docs",
    "eval",
    "scripts",
    "src",
    "train",
]
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "data/private",
    "results",
    "graphify-out",
    "checkpoints",
    "models",
    "adapters",
    "outputs",
}


@dataclass
class RemoteConfig:
    host: str
    user: str
    root: str
    max_rows: int
    run_download_on_login_node: bool
    skip_data_prep_submit: bool
    live_prompts: bool


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    log_dir = repo_root / "results" / "remote_setup"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"narval_paramiko_{datetime.now():%Y%m%d_%H%M%S}.log"

    config = RemoteConfig(
        host=args.host,
        user=args.user,
        root=args.remote_root,
        max_rows=args.max_rows,
        run_download_on_login_node=args.run_download_on_login_node,
        skip_data_prep_submit=args.skip_data_prep_submit,
        live_prompts=args.live_prompts,
    )

    print("Narval automated setup for lora_health")
    print("Credentials are prompted here and kept in memory only.")
    print(f"Local non-secret log: {log_path}")
    log(log_path, "started_waiting_for_credentials")
    password = "" if config.live_prompts else getpass.getpass("Narval password: ")
    mfa_code = "" if config.live_prompts else getpass.getpass("Narval MFA code: ")

    client = connect(config, password, mfa_code)
    try:
        log(log_path, "connected")
        run(client, config, log_path, f"mkdir -p '{config.root}/tmp' '{config.root}/code'")
        archive = build_archive(repo_root)
        try:
            upload_archive(client, archive, f"{config.root}/tmp/code_upload.tgz", log_path)
        finally:
            archive.unlink(missing_ok=True)

        run(client, config, log_path, f"tar -xzf '{config.root}/tmp/code_upload.tgz' -C '{config.root}/code'")
        run(client, config, log_path, f"cd '{config.root}/code' && bash scripts/narval_bootstrap.sh", timeout=1800)

        if config.run_download_on_login_node:
            run(
                client,
                config,
                log_path,
                f"cd '{config.root}/code' && MAX_ROWS={config.max_rows} bash scripts/narval_pull_data.sh",
                timeout=7200,
            )
        elif not config.skip_data_prep_submit:
            run(
                client,
                config,
                log_path,
                f"cd '{config.root}' && MAX_ROWS={config.max_rows} sbatch code/scripts/submit_narval_data_prep.sh",
            )

        run(client, config, log_path, f"cd '{config.root}' && bash code/scripts/narval_status.sh", timeout=600)
        print(f"Done. Non-secret log: {log_path}")
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate Narval setup with in-memory password/MFA prompts.")
    parser.add_argument("--host", default="narval.alliancecan.ca")
    parser.add_argument("--user", default="syin94")
    parser.add_argument("--remote-root", default="/home/syin94/scratch/lora_health")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--run-download-on-login-node", action="store_true")
    parser.add_argument("--skip-data-prep-submit", action="store_true")
    parser.add_argument("--live-prompts", action="store_true", help="Ask for each SSH keyboard-interactive prompt live.")
    return parser.parse_args()


def connect(config: RemoteConfig, password: str, mfa_code: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    transport = paramiko.Transport((config.host, 22))
    transport.start_client(timeout=30)

    used = {"password": False, "mfa": False}

    def handler(title: str, instructions: str, prompts: list[tuple[str, bool]]) -> list[str]:
        answers: list[str] = []
        print_prompt(title, instructions, prompts)
        for prompt, _echo in prompts:
            if config.live_prompts:
                answers.append(getpass.getpass(prompt or "SSH response: "))
                continue
            label = prompt.lower()
            if "password" in label or not used["password"]:
                answers.append(password)
                used["password"] = True
            elif any(key in label for key in ["mfa", "verification", "code", "passcode", "token", "otp", "duo"]):
                answers.append(mfa_code)
                used["mfa"] = True
            elif not used["mfa"]:
                answers.append(mfa_code)
                used["mfa"] = True
            else:
                answers.append("")
        return answers

    try:
        print("Trying password authentication...")
        transport.auth_password(config.user, password, fallback=False)
    except PartialAuthentication as exc:
        print(f"Password accepted; continuing with: {exc.allowed_types}")
        if "keyboard-interactive" not in exc.allowed_types:
            raise RuntimeError(f"Password auth was partial but keyboard-interactive was not offered: {exc.allowed_types}") from exc
        transport.auth_interactive(config.user, handler)
    except AuthenticationException:
        print("Password authentication did not complete; trying keyboard-interactive flow...")
        if not transport.is_active():
            transport.close()
            transport = paramiko.Transport((config.host, 22))
            transport.start_client(timeout=30)
        transport.auth_interactive(config.user, handler)

    if not transport.is_authenticated():
        raise RuntimeError("Narval authentication failed")

    client._transport = transport
    return client


def print_prompt(title: str, instructions: str, prompts: list[tuple[str, bool]]) -> None:
    parts = [part for part in [title.strip(), instructions.strip()] if part]
    for prompt, _echo in prompts:
        parts.append(prompt.strip())
    if parts:
        print("SSH prompt: " + " | ".join(parts))


def build_archive(repo_root: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix="lora_health_code_", suffix=".tgz")
    os.close(fd)
    archive = Path(name)

    with tarfile.open(archive, "w:gz") as tar:
        for item in SAFE_ITEMS:
            path = repo_root / item
            if not path.exists():
                continue
            add_safe(tar, repo_root, path)
    return archive


def add_safe(tar: tarfile.TarFile, repo_root: Path, path: Path) -> None:
    rel = path.relative_to(repo_root).as_posix()
    if should_skip(rel):
        return
    if path.is_dir():
        for child in path.iterdir():
            add_safe(tar, repo_root, child)
    else:
        tar.add(path, arcname=rel)


def should_skip(rel: str) -> bool:
    return any(rel == part or rel.startswith(f"{part}/") for part in SKIP_PARTS)


def upload_archive(client: paramiko.SSHClient, local_path: Path, remote_path: str, log_path: Path) -> None:
    log(log_path, f"upload {local_path} -> {remote_path}")
    with client.open_sftp() as sftp:
        sftp.put(str(local_path), remote_path)


def run(
    client: paramiko.SSHClient,
    config: RemoteConfig,
    log_path: Path,
    command: str,
    timeout: int = 900,
) -> None:
    guard_command = (
        f"test \"${{PWD}}\" != '/home/syin94/scratch/MEng_Project' && "
        f"case '{config.root}' in /home/syin94/scratch/lora_health*) ;; *) exit 90 ;; esac && "
        + command
    )
    log(log_path, f"$ {command}")
    print(f"\n== remote ==\n{command}")
    stdin, stdout, stderr = client.exec_command(guard_command, get_pty=True, timeout=timeout)
    del stdin

    start = time.time()
    chunks: list[str] = []
    err_chunks: list[str] = []
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            text = stdout.channel.recv(4096).decode("utf-8", errors="replace")
            print(text, end="")
            chunks.append(text)
        if stdout.channel.recv_stderr_ready():
            text = stdout.channel.recv_stderr(4096).decode("utf-8", errors="replace")
            print(text, end="")
            err_chunks.append(text)
        if time.time() - start > timeout:
            raise TimeoutError(f"Remote command timed out after {timeout}s: {command}")
        time.sleep(0.2)

    chunks.append(stdout.read().decode("utf-8", errors="replace"))
    err_chunks.append(stderr.read().decode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    output = "".join(chunks)
    error = "".join(err_chunks)
    if output:
        log(log_path, output.rstrip())
    if error:
        log(log_path, error.rstrip())
    log(log_path, f"exit={code}")
    if code != 0:
        raise RuntimeError(f"Remote command failed with exit {code}: {command}")


def log(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")


if __name__ == "__main__":
    main()
