from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from backend.app.crypto import decrypt_env, derive_key
from cli.envsync.main import app

runner = CliRunner()


def test_push_command_encrypts_and_posts(tmp_path, monkeypatch):
    project_id = "project-123"
    passphrase = "correct horse battery staple"
    token = "jwt-token"
    env_text = "API_KEY=secret\nDEBUG=true\n# comment\nEMPTY=\n"

    (tmp_path / ".envsync.json").write_text(f'{{"project_id": "{project_id}"}}', encoding="utf-8")
    (tmp_path / ".env").write_text(env_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVSYNC_TOKEN", token)
    monkeypatch.setenv("ENVSYNC_PASS", passphrase)
    monkeypatch.setenv("ENVSYNC_API", "http://api.local")

    captured: dict[str, object] = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        class Response:
            def raise_for_status(self):
                return None

        return Response()

    monkeypatch.setattr("cli.envsync.main.httpx.post", fake_post)

    result = runner.invoke(app, ["push", "--branch", "feat/auth"])

    assert result.exit_code == 0
    assert "Pushed 3 keys" in result.stdout
    assert captured["url"] == "http://api.local/env/project-123/feat/auth"
    assert captured["headers"] == {"Authorization": f"Bearer {token}"}
    assert captured["timeout"] == 30.0

    payload = captured["json"]
    assert payload["key_names"] == ["API_KEY", "DEBUG", "EMPTY"]
    assert decrypt_env(payload["ciphertext"], derive_key(passphrase, project_id)) == env_text


def test_pull_command_writes_env_file(tmp_path, monkeypatch):
    project_id = "project-123"
    passphrase = "correct horse battery staple"
    token = "jwt-token"
    plaintext = "API_KEY=secret\nDEBUG=true\n"
    key = derive_key(passphrase, project_id)
    ciphertext = ""

    from backend.app.crypto import encrypt_env

    ciphertext = encrypt_env(plaintext, key)

    (tmp_path / ".envsync.json").write_text(f'{{"project_id": "{project_id}"}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVSYNC_TOKEN", token)
    monkeypatch.setenv("ENVSYNC_PASS", passphrase)
    monkeypatch.setenv("ENVSYNC_API", "http://api.local")

    captured: dict[str, object] = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ciphertext": ciphertext, "key_names": ["API_KEY", "DEBUG"], "version": 1}

        return Response()

    monkeypatch.setattr("cli.envsync.main.httpx.get", fake_get)

    result = runner.invoke(app, ["pull", "--branch", "feat/auth"])

    assert result.exit_code == 0
    assert "updated from feat/auth" in result.stdout
    assert captured["url"] == "http://api.local/env/project-123/feat/auth"
    assert captured["headers"] == {"Authorization": f"Bearer {token}"}
    assert captured["timeout"] == 30.0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == plaintext


def test_diff_command_reports_drift(tmp_path, monkeypatch):
    project_id = "project-123"
    token = "jwt-token"

    (tmp_path / ".envsync.json").write_text(f'{{"project_id": "{project_id}"}}', encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=secret\nDEBUG=true\nEXTRA_ONLY=value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVSYNC_TOKEN", token)
    monkeypatch.setenv("ENVSYNC_API", "http://api.local")

    captured: dict[str, object] = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "missing_locally": ["STRIPE_SECRET"],
                    "extra_locally": ["EXTRA_ONLY"],
                    "in_sync": False,
                }

        return Response()

    monkeypatch.setattr("cli.envsync.main.httpx.get", fake_get)

    result = runner.invoke(app, ["diff", "--branch", "feat/auth"])

    assert result.exit_code == 0
    assert "Drift for feat/auth" in result.stdout
    assert "STRIPE_SECRET" in result.stdout
    assert "EXTRA_ONLY" in result.stdout
    assert captured["url"] == "http://api.local/env/project-123/feat/auth/diff"
    assert captured["headers"] == {"Authorization": f"Bearer {token}"}
    assert captured["timeout"] == 30.0
    assert captured["params"] == [("local_keys", "API_KEY"), ("local_keys", "DEBUG"), ("local_keys", "EXTRA_ONLY")]
