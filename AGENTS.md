# AGENTS.md

## Commands

```bash
uv sync                    # install deps into .venv
uv run python src/main.py  # run the script (must be invoked from repo root)
```

There are **no test, lint, or typecheck commands** configured in this repo. Do not try to run them.

## Architecture

- Single script at `src/main.py` — the only entry point. There is no package build or CLI entrypoint.
- `src/` is on `sys.path` only because Python adds the script's directory. Imports like `from fetcher import Fetcher` work for this reason. Do not restructure into an installable package without adjusting all imports.
- Three sub-packages: `fetcher/`, `sender/`, `models/` — each re-exports via `__init__.py`.

## Runtime requirements

- **Python 3.12+** (`.python-version`).
- Two **gitignored** config files must exist locally before running:
  - `config/.env` — Infisical bootstrap token, project ID, slug, environment. Missing → `sys.exit(1)`.
  - `config/gcs.json` — GCS service account key (set as `GOOGLE_APPLICATION_CREDENTIALS` env var at runtime). Missing → `RuntimeError` inside Fetcher.
- All other secrets come from **Infisical** (EU host: `https://eu.infisical.com`) at paths `/SMTP`, `/prtpe`, `/prtso`, `/solid`, `/bige`.

## Hardcoded values to be aware of

- **SMTP host/port**: `smtp.gmail.com:587` with STARTTLS — hardcoded in `main.py`, not from Infisical. Only credentials (username, password, from/to) come from secrets.
- **SFTP connection timeout**: 30 seconds (hardcoded in `fetcher.py`).
- **Log file**: `app.log` in the working directory, append mode. Also logs to console.
- **`local_path`** from secrets must be an existing directory before the run — Fetcher validates this and raises `RuntimeError` if missing.

## SFTP / key auth quirks

- **Key-based auth only** (no password fallback). The script tries `paramiko.RSAKey` first, then `paramiko.Ed25519Key`.
- If RSA is used, the key **must be exactly 4096 bits** — the server rejects other sizes and the script hard-fails.
- `PATH_TO_KEY` and `LOCAL_PATH` from Infisical secrets are expanded with `os.path.expanduser`, so `~` paths work.
- A 1-second `time.sleep(1)` is inserted between each file in the download loop.

## Error handling pattern

- Both `main.py` and `fetcher.py` define a `_safe_notify` helper — email delivery failures are caught and logged but never propagated.
- Per-file failures (download, upload, delete) are tracked individually; a single file failure does not abort the BIP run. Remote deletion is skipped if GCS upload failed.

## BIP job list

`BIP_JOBS` in `main.py` is a list of `(label, infisical_secret_path)` tuples. Order = run order. Commented-out `*_TEST` entries exist at the top and can be swapped in for dry runs.
