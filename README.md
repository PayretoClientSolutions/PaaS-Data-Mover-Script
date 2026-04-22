# move-it

Scheduled job that pulls report files from **SFTP** (one integration per BIP), uploads them to **Google Cloud Storage**, then removes the local copy after a successful upload and deletes the file on the remote server.

## What it does

1. Loads a small set of variables from `config/.env` and connects to **Infisical** (EU: `https://eu.infisical.com`) to load the rest of the secrets.
2. Configures **SMTP** from the `/SMTP` secret path and builds an email sender for error notifications.
3. For each configured BIP, loads SFTP and GCS-related secrets from that BIP’s Infisical folder, then runs the **Fetcher**:
   - Connects with **key-based SSH/SFTP** (private key path and optional key passphrase from secrets).
   - Lists files in the remote directory (default `/REPORTS`), keeps those matching the target extension (default `.csv`).
   - Downloads each file to a local directory, uploads it to the **GCS bucket** named in secrets, deletes the local file if upload succeeds, then removes the remote file.

The app is intended to run on a **Linux VM** under **cron**, similar to other batch jobs.

## Project layout

| Path | Role |
|------|------|
| `config/.env` | Infisical token, project identifiers, environment (not committed; create locally). |
| `config/gcs.json` | GCS service account key; referenced as `GOOGLE_APPLICATION_CREDENTIALS` when fetching. |
| `src/main.py` | Entry point: Infisical, SMTP, per-BIP `fetch_and_move`. |
| `src/fetcher/` | SFTP download + GCS upload logic. |
| `src/sender/` | SMTP helper for alerts. |
| `src/models/` | `SFTPConfig`, `EmailConfig`, `InfisicalConfig`. |

Logs go to **`app.log`** in the process working directory and to the console.

## Prerequisites

- **Python 3.12+** (see `requires-python` in `pyproject.toml`).
- **[uv](https://github.com/astral-sh/uv)** (or another way to install dependencies from `pyproject.toml`).
- Network access to Infisical, SFTP endpoints, Gmail SMTP (as configured in code), and GCS.
- On the VM: SSH private key file paths referenced in Infisical must exist and be readable. The SFTP side expects **Ed25519** or **4096-bit RSA** keys where applicable.

## Configuration

### `config/.env` (local)

Used to bootstrap Infisical. Typical variables (names must match what `src/main.py` reads):

- `INFISICAL_TOKEN`
- `INFISICAL_PROJECT_ID`
- `INFISICAL_PROJECT_SLUG` — project slug
- `INFISICAL_ENVIRONMENT` — defaults to `dev` if unset

### Infisical: `/SMTP`

Secrets supply Gmail (or compatible) SMTP credentials and message defaults:

- `USERNAME`, `PASSWORD`, `FROM_ADDR`
- `TO_ADDRS` — comma-separated recipient list
- `SUBJECT_PREFIX`, `APP_NAME`

SMTP host and port are set in code (`smtp.gmail.com`, `587`, STARTTLS).

### Infisical: per-BIP folders

The app loads secrets from paths such as `/prtpe`, `/prtso`, `/solid`, and `/bige` (and separate `*_test` paths for test environments; whether those runs are enabled depends on `main.py`).

Each BIP folder should provide keys that map to **SFTPConfig**, for example:

- `HOSTNAME`, `USERNAME`, `PORT`, `PASSWORD`
- `PATH_TO_KEY` — local path to the SFTP private key
- `LOCAL_PATH` — directory for temporary downloads (must exist before the run)
- `BUCKET_NAME` — GCS bucket for uploads

Optional overrides (defaults are in `SFTPConfig` in `src/models/models.py`):

- `TARGET_FILE_TYPE` / remote path — only if you extend secrets to pass them through (today defaults are `.csv` and `/REPORTS` unless your Infisical mapping adds them).

GCS authentication uses **`config/gcs.json`** at the repository root’s `config/` directory, not a secret path inside each BIP dict.

## BIPs in the current script

`main.py` runs the **`*_TEST`** Infisical folders first (**PRTPE_TEST**, **PRTSO_TEST**, **SOLID_TEST**, **BIGE_TEST**), then production (**PRTPE**, **PRTSO**, **SOLID**, **BIGE**). All entries live in `BIP_JOBS`; remove or reorder rows there if you want to skip test or change run order.

## Logging and operations

- **Log file**: `app.log` (append). Ensure the cron working directory is predictable, or consider switching to an absolute log path in code if logs go missing.
- **Monitoring**: Watch for SFTP/GCS failures and email alerts; keep disk space available under each BIP’s `LOCAL_PATH`.
- **GCS**: Objects are uploaded using the **file name only** as the blob name; same name in the same bucket will overwrite previous objects.

## Dependencies

Declared in `pyproject.toml`, including:

- `google-cloud-storage` — GCS uploads
- `infisicalsdk` — secrets
- `paramiko` — SFTP
- `python-dotenv` — load `config/.env`

Install with uv from the repo root, for example:

```bash
uv sync
```

From the repository root (Python puts `src/` on the module path when running `src/main.py`):

```bash
uv run python src/main.py
```

Adjust if your deployment uses a different working directory or wrapper script.
