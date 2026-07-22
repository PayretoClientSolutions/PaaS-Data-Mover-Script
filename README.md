# move-it

`move-it` is a scheduled batch job that moves report files from partner SFTP servers to Google Cloud Storage (GCS). Each configured BIP is processed independently so one failed integration does not stop the remaining jobs.

## Transfer flow

For each BIP, the script:

1. Connects to SFTP using a local private key.
2. Lists the configured remote directory and selects files matching the configured suffix.
3. Downloads each matching file to an existing local staging directory.
4. Uploads the file to the configured GCS bucket using the filename as the blob name.
5. Deletes the local copy after a successful upload.
6. Deletes the remote file after the local copy has been removed.

An upload failure retains both the local and remote copies. A remote deletion failure is recorded but does not stop later files. Reusing a filename in the same bucket overwrites the existing GCS object.

The script sends notifications for operational failures and BIPs with no matching files, then sends an HTML and plain-text summary after all BIPs have run. Notification failures are logged without aborting processing.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Network access to the EU Infisical host, configured SFTP servers, GCS, and `smtp.gmail.com:587`
- Readable SFTP private keys on the machine running the job
- A GCS service-account credentials file

Install the dependencies from the repository root:

```bash
uv sync
```

## Configuration

The two local configuration files below are gitignored and must exist before the script starts.

### `config/.env`

This file bootstraps the Infisical SDK:

```dotenv
INFISICAL_TOKEN=
INFISICAL_PROJECT_ID=
INFISICAL_PROJECT_SLUG=
INFISICAL_ENVIRONMENT=dev
```

`INFISICAL_ENVIRONMENT` is optional and defaults to `dev`. All remaining secrets are loaded from `https://eu.infisical.com`.

### `config/gcs.json`

Place the GCS service-account credentials at `config/gcs.json`. The script sets this path as `GOOGLE_APPLICATION_CREDENTIALS` while initializing each BIP's GCS client.

### Infisical `/SMTP`

The `/SMTP` path supplies:

- `USERNAME`
- `PASSWORD`
- `FROM_ADDR`
- `TO_ADDRS`, as a comma-separated list
- `SUBJECT_PREFIX`
- `APP_NAME`

The SMTP server is fixed to Gmail on port 587 with STARTTLS.

### Infisical BIP paths

Production jobs currently run in this order:

| BIP | Secret path |
| --- | --- |
| PRTPE | `/prtpe` |
| PRTSO | `/prtso` |
| SOLID | `/solid` |
| BIGE | `/bige` |

Each path supports these values:

| Key | Purpose | Default |
| --- | --- | --- |
| `HOSTNAME` | SFTP hostname | none |
| `USERNAME` | SFTP username | none |
| `PORT` | SFTP port | `22` |
| `PASSWORD` | Private-key passphrase, not an SFTP password | empty |
| `PATH_TO_KEY` | Local private-key path | required |
| `LOCAL_PATH` | Existing local staging directory | `.` |
| `BUCKET_NAME` | Destination GCS bucket | none |
| `TARGET_FILE_TYPE` | Filename suffix to process | `.csv` |
| `REMOTE_PATH` | Remote directory to scan | `/REPORTS` |

`PATH_TO_KEY` and `LOCAL_PATH` expand `~`. Authentication is key-only: RSA is attempted before Ed25519, and RSA keys must be exactly 4096 bits.

Enabled jobs and their order are controlled by `BIP_JOBS` in `src/main.py`. Commented entries are available for the separate `*_test` Infisical paths.

## Running

Run the entrypoint directly from the repository root:

```bash
uv run python src/main.py
```

Direct execution is required by the current top-level imports under `src/`; the project does not define an installed CLI entrypoint.

This command performs real downloads, uploads, deletions, and email sends. Use test BIP entries and test credentials when validating changes rather than running the production job list.

The script appends logs to `app.log` at the repository root and also writes them to the console. Per-file and per-BIP failures are included in the final summary instead of terminating the full run.

## Project layout

| Path | Responsibility |
| --- | --- |
| `src/main.py` | Infisical setup, job orchestration, and summary generation |
| `src/fetcher/` | SFTP download, GCS upload, and file cleanup |
| `src/sender/` | SMTP messages |
| `src/models/` | Runtime configuration and result dataclasses |

No automated test, lint, formatter, or typecheck command is currently configured.
