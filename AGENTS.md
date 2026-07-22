# AGENTS.md

## Commands

```bash
uv sync
uv run python src/main.py
```

- Run commands from the repository root; direct execution puts `src/` on `sys.path` for imports such as `from fetcher import Fetcher`.
- No test, lint, formatter, or typecheck commands are configured.

## Architecture

- `src/main.py` is the only entry point; there is no package build or CLI entrypoint.
- `fetcher/`, `sender/`, and `models/` are top-level imports only under direct script execution. Packaging or changing invocation requires adjusting imports or `PYTHONPATH`.
- `BIP_JOBS` in `src/main.py` controls enabled integrations and run order. Commented `*_TEST` entries point to separate Infisical paths.

## Runtime Setup

- Python 3.12+ is required by both `.python-version` and `pyproject.toml`.
- `config/.env` and `config/gcs.json` are gitignored and required; either missing file causes `main.py` to exit before BIP processing.
- `config/.env` bootstraps Infisical with `INFISICAL_TOKEN`, `INFISICAL_PROJECT_ID`, `INFISICAL_PROJECT_SLUG`, and optional `INFISICAL_ENVIRONMENT` (default `dev`). Do not commit secret values.
- Remaining secrets come from the EU Infisical host at `/SMTP` and the paths named by `BIP_JOBS`.
- Each BIP's `LOCAL_PATH` must already exist. `PATH_TO_KEY` and `LOCAL_PATH` expand `~`.
- GCS credentials are exposed through `GOOGLE_APPLICATION_CREDENTIALS` during `Fetcher` initialization.

## Transfer Constraints

- SFTP is key-only: RSA is attempted before Ed25519, and RSA keys must be exactly 4096 bits. The Infisical `PASSWORD` value is the private-key passphrase, not an SFTP password.
- Defaults are remote path `/REPORTS`, suffix `.csv`, port `22`, and a 30-second SSH connection timeout; BIP secrets can override the first three.
- Uploads use only the filename as the GCS blob name, so an existing object with that name is overwritten.
- A successful upload deletes the local file, then the remote file. Upload failure retains both copies; remote deletion failure is recorded without aborting later files.
- Per-file and per-BIP failures are summarized rather than aborting the full run. Notification-email failures are logged and suppressed.

## Operations

- SMTP is hardcoded to `smtp.gmail.com:587` with STARTTLS; Infisical supplies credentials, addresses, and subject metadata.
- Logs append to repository-root `app.log` and also go to the console.
- The runtime performs real SFTP downloads, GCS uploads, remote deletions, and email sends; do not use the main command as a routine verification check without configured test integrations.
