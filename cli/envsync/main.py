from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from backend.app.crypto import decrypt_env, derive_key, encrypt_env

app = typer.Typer(add_completion=False)
console = Console()


def get_config() -> dict[str, str | None]:
    """Read runtime config from environment variables."""
    return {
        "api_url": os.getenv("ENVSYNC_API", "http://127.0.0.1:8000"),
        "token": os.getenv("ENVSYNC_TOKEN"),
        "passphrase": os.getenv("ENVSYNC_PASS"),
    }


def _get_git_branch() -> str:
    """Return the current git branch, falling back to a safe default."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        return branch or os.getenv("ENVSYNC_BRANCH", "main")
    except (OSError, subprocess.CalledProcessError):
        return os.getenv("ENVSYNC_BRANCH", "main")


def _find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".envsync.json").exists():
            return candidate
    return current


def _get_project_id() -> str:
    """Read the project ID from .envsync.json in the project root."""
    config_path = _find_project_root() / ".envsync.json"
    if not config_path.exists():
        raise typer.Exit(code=1)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    project_id = data.get("project_id")
    if not project_id:
        raise typer.Exit(code=1)
    return project_id


def _require_config_value(value: str | None, label: str) -> str:
    if not value:
        console.print(f"[red]Missing {label}[/red]")
        raise typer.Exit(code=1)
    return value


def _parse_key_names(plaintext: str) -> list[str]:
    key_names: list[str] = []
    for line in plaintext.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key_names.append(stripped.split("=", 1)[0].strip())
    return key_names


def _read_local_key_names(env_file: str = ".env") -> list[str]:
    env_path = Path(env_file)
    if not env_path.exists():
        console.print(f"[red]✗ {env_file} not found[/red]")
        raise typer.Exit(code=1)
    return _parse_key_names(env_path.read_text(encoding="utf-8"))


@app.command()
def push(
    branch: str = typer.Option(None, help="Branch name (defaults to current git branch)"),
    env_file: str = typer.Option(".env", help="Path to .env file"),
) -> None:
    """Encrypt and push your .env to the vault."""
    cfg = get_config()
    branch = branch or _get_git_branch()
    token = _require_config_value(cfg["token"], "ENVSYNC_TOKEN")
    passphrase = _require_config_value(cfg["passphrase"], "ENVSYNC_PASS")

    env_path = Path(env_file)
    if not env_path.exists():
        console.print(f"[red]✗ {env_file} not found[/red]")
        raise typer.Exit(code=1)

    plaintext = env_path.read_text(encoding="utf-8")
    key_names = _parse_key_names(plaintext)
    project_id = _get_project_id()
    key = derive_key(passphrase, project_id)
    ciphertext = encrypt_env(plaintext, key)

    response = httpx.post(
        f"{cfg['api_url']}/env/{project_id}/{branch}",
        json={"ciphertext": ciphertext, "key_names": key_names},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    console.print(f"[green]✓ Pushed {len(key_names)} keys to {branch}[/green]")


@app.command()
def pull(branch: str = typer.Option(None, help="Branch name (defaults to current git branch)")) -> None:
    """Pull and decrypt the latest .env for a branch."""
    cfg = get_config()
    branch = branch or _get_git_branch()
    token = _require_config_value(cfg["token"], "ENVSYNC_TOKEN")
    passphrase = _require_config_value(cfg["passphrase"], "ENVSYNC_PASS")
    project_id = _get_project_id()

    response = httpx.get(
        f"{cfg['api_url']}/env/{project_id}/{branch}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    response.raise_for_status()

    key = derive_key(passphrase, project_id)
    plaintext = decrypt_env(response.json()["ciphertext"], key)
    Path(".env").write_text(plaintext, encoding="utf-8")
    console.print(f"[green]✓ .env updated from {branch}[/green]")


@app.command()
def diff(branch: str = typer.Option(None, help="Branch name (defaults to current git branch)")) -> None:
    """Show drift between local .env and the server."""
    cfg = get_config()
    branch = branch or _get_git_branch()
    token = _require_config_value(cfg["token"], "ENVSYNC_TOKEN")
    project_id = _get_project_id()
    local_keys = _read_local_key_names()

    response = httpx.get(
        f"{cfg['api_url']}/env/{project_id}/{branch}/diff",
        params=[("local_keys", key) for key in local_keys],
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    drift = response.json()

    table = Table(title=f"Drift for {branch}")
    table.add_column("Category")
    table.add_column("Keys")
    table.add_row("Missing locally", ", ".join(drift["missing_locally"]) or "-")
    table.add_row("Extra locally", ", ".join(drift["extra_locally"]) or "-")
    table.add_row("In sync", "yes" if drift["in_sync"] else "no")
    console.print(table)


if __name__ == "__main__":
    app()
