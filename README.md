# EnvSync

EnvSync is an encrypted environment vault for teams that want to store, pull, and compare `.env` files without exposing plaintext on the server.

The design is intentionally simple in this phase:

- The CLI encrypts `.env` content locally.
- The backend stores only ciphertext and key names.
- Drift detection compares the key names on both sides without decrypting server data.
- The server never receives or stores the passphrase.

## Project Layout

```text
envsync/
├─ backend/
│  └─ app/
│     ├─ auth.py
│     ├─ audit.py
│     ├─ crypto.py
│     ├─ db.py
│     ├─ main.py
│     ├─ models.py
│     └─ routes/
│        └─ env.py
├─ cli/
│  └─ envsync/
│     └─ main.py
├─ tests/
├─ pyproject.toml
└─ README.md
```

## What Exists Today

- `backend/app/crypto.py` contains deterministic key derivation plus Fernet encrypt/decrypt helpers.
- `backend/app/models.py` defines the stored env snapshot and audit entry models.
- `backend/app/routes/env.py` exposes push, pull, and drift routes.
- `cli/envsync/main.py` exposes `push`, `pull`, and `diff` commands.
- `backend/app/db.py` currently uses an in-memory store so the project can be exercised without MongoDB.

## Requirements

- Python 3.14+
- Git, if you want branch auto-detection in the CLI
- A shell where you can set environment variables

## Quick Start

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install the project in editable mode with test dependencies.

```powershell
python -m pip install -e .[dev]
```

3. Run the test suite.

```powershell
pytest
```

4. Start the API server.

```powershell
uvicorn backend.app.main:app --reload
```

5. In a second terminal, set the CLI runtime variables.

```powershell
$env:ENVSYNC_API = "http://127.0.0.1:8000"
$env:ENVSYNC_TOKEN = "your-jwt-token"
$env:ENVSYNC_PASS = "your-local-passphrase"
```

6. Add a project file in the repository root.

Create a `.envsync.json` file that contains your project identifier.

```json
{
  "project_id": "project-123"
}
```

7. Prepare a local `.env` file.

```env
API_KEY=secret
DEBUG=true
```

8. Push the encrypted env file.

```powershell
envsync push --branch main
```

9. Pull the latest encrypted env file back down.

```powershell
envsync pull --branch main
```

10. Check drift between local keys and the server.

```powershell
envsync diff --branch main
```

## CLI Commands

### `envsync push`

Encrypts the local `.env` file and sends ciphertext plus key names to the backend.

Useful options:

- `--branch`: override the detected git branch.
- `--env-file`: point at a different env file.

### `envsync pull`

Fetches the latest ciphertext for a branch, decrypts it locally, and writes `.env`.

Useful option:

- `--branch`: override the detected git branch.

### `envsync diff`

Reads local key names from `.env`, asks the backend for drift, and prints a short summary table.

Useful option:

- `--branch`: override the detected git branch.

## API Endpoints

### `POST /env/{project_id}/{branch}`

Stores an encrypted `.env` snapshot.

Request body:

```json
{
  "ciphertext": "...",
  "key_names": ["API_KEY", "DEBUG"]
}
```

### `GET /env/{project_id}/{branch}`

Returns the latest stored ciphertext and metadata for a branch.

### `GET /env/{project_id}/{branch}/diff`

Returns drift information for a branch.

Query parameter:

- `local_keys`: repeatable list of local key names.

Example response:

```json
{
  "missing_locally": ["STRIPE_SECRET"],
  "extra_locally": ["EXTRA_ONLY"],
  "in_sync": false
}
```

## Security Model

- The passphrase stays local and should come from the developer's shell or a keyring-backed secret store.
- The backend stores ciphertext only.
- The backend stores key names for drift detection, but not values.
- Audit events are recorded separately from vault snapshots.

## Development Notes

- The in-memory database is intentionally minimal for the current phase.
- JWT auth and RBAC are still stubbed in the codebase and should be replaced before production use.
- The route layer is small by design so later phases can add MongoDB, real auth, and a dashboard without reshaping the current API.

## Testing

Run all tests with:

```powershell
pytest
```

If you only want the CLI tests or backend route tests, use the relevant file targets:

```powershell
pytest tests/test_cli.py
pytest tests/test_diff.py
pytest tests/test_routes.py
```

## Best Practices to Keep

- Do not store the passphrase on the server.
- Keep plaintext out of request logs.
- Treat `key_names` as metadata only.
- Keep new features behind tests before expanding the architecture.

## Next Steps

The next phase should add real JWT authentication and role-based authorization, then replace the in-memory store with MongoDB.
