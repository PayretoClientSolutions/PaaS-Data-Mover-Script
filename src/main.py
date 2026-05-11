import html
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient

from fetcher import Fetcher
from models import BIPSummary, SFTPConfig
from models.models import EmailConfig, InfisicalConfig
from sender import Sender

# BIP label (for logs / email) and Infisical secret_path. Order is run order.
BIP_JOBS: list[tuple[str, str]] = [
    # ("PRTPE_TEST", "/prtpe_test"),
    # ("PRTSO_TEST", "/prtso_test"),
    # ("SOLID_TEST", "/solid_test"),
    # ("BIGE_TEST", "/bige_test"),
    ("PRTPE", "/prtpe"),
    ("PRTSO", "/prtso"),
    ("SOLID", "/solid"),
    ("BIGE", "/bige"),
]


def init_logger() -> None:
    """
    Initializes the logger for the whole script
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(
                Path(__file__).resolve().parents[1] / "app.log", mode="a"
            ),
            logging.StreamHandler(),  # Logs to console.
        ],
    )


def init_sender(
    host: str,
    port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addrs: list[str],
    use_tls: bool,
    use_ssl: bool,
    subject_prefix: str,
    app_name: str,
) -> Sender:
    """
    Initializes the Sender class for email notifications.
    Returns:
        Sender: An instance of the Sender class configured with SMTP settings.
    """
    email_cfg = EmailConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        from_addr=from_addr,
        to_addrs=to_addrs,
        use_tls=use_tls,
        use_ssl=use_ssl,
        subject_prefix=subject_prefix,
        app_name=app_name,
    )

    return Sender(config=email_cfg)


def init_infisical_client() -> InfisicalConfig:
    """
    Initializes the Infisical SDK client for fetching secrets.
    Returns:
        InfisicalConfig: An instance of the InfisicalConfig configured with the necessary parameters.
    """

    # read environment variables from .env file
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
    if not env_path.exists():
        logging.error(f"Environment file not found at: {env_path}")
        sys.exit(1)

    load_dotenv(env_path)

    try:
        logging.info("Fetching secrets from Infisical...")
        client = InfisicalSDKClient(
            host="https://eu.infisical.com", token=os.environ.get("INFISICAL_TOKEN", "")
        )

        project_id = os.environ.get("INFISICAL_PROJECT_ID", "")
        project_slug = os.environ.get("INFISICAL_PROJECT_SLUG", "")
        environment_slug = os.environ.get("INFISICAL_ENVIRONMENT", "dev")

        return InfisicalConfig(
            client=client,
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
        )
    except Exception as e:
        logging.error(f"Error initializing Infisical client: {e}")
        raise


def _safe_notify(email_sender: Sender, *, subject: str, body: str) -> None:
    """
    Sends an email notification without masking the original error path
    if SMTP delivery fails.
    """
    try:
        email_sender.send(subject=subject, body=body)
    except Exception as notify_error:
        logging.error(f"Failed to send notification email: {notify_error}")


def _secrets_dict_at_path(
    client: InfisicalSDKClient,
    *,
    project_id: str,
    project_slug: str,
    environment_slug: str,
    secret_path: str,
) -> dict[str, str]:
    """
    Fetches secrets from Infisical at a given path.
    Returns:
        dict[str, str]: A dictionary of secrets with the secret key as the key and the secret value as the value.
    """
    rows = client.secrets.list_secrets(
        project_id=project_id,
        project_slug=project_slug,
        environment_slug=environment_slug,
        secret_path=secret_path,
    ).secrets
    return {row.secretKey: row.secretValue for row in rows}


def _status_emoji(status: str) -> str:
    return {
        "success": "&#x2705;",
        "partial": "&#x26A0;",
        "failed": "&#x274C;",
        "no_files": "&#x26AA;",
    }.get(status, "&#x2753;")


def _build_summary_text(summaries: list[BIPSummary]) -> str:
    """Build plain-text fallback body for the summary email."""
    lines = [
        "PaaS Data Extraction Script - Hourly Summary",
        "=====================",
        "",
    ]
    for s in summaries:
        lines.append(f"BIP: {s.bip_name}")
        lines.append(f"  Status: {s.status}")
        lines.append(f"  Files found: {s.files_found}")
        lines.append(f"  Downloaded: {len(s.downloaded)}")
        lines.append(f"  Deleted: {len(s.deleted)}")
        lines.append(f"  Failed: {s.files_failed}")
        lines.append(f"  Duration: {s.duration_s:.1f}s")
        if s.failed_downloads or s.failed_deletions:
            lines.append("  Failed files:")
            for fr in s.failed_downloads + s.failed_deletions:
                lines.append(f"    - {fr.name} ({fr.stage}): {fr.error_message or ''}")
        lines.append("")
    return "\n".join(lines)


def _build_summary_html(summaries: list[BIPSummary]) -> str:
    """
    Build an HTML summary email body.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_html = []
    for s in summaries:
        rows_html.append(
            f"<tr>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;'><strong>{html.escape(s.bip_name)}</strong></td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;'>{s.files_found}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;'>{len(s.downloaded)}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;'>{len(s.deleted)}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;'>{s.files_failed}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;'>{s.duration_s:.1f}s</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;font-size:20px;'>{_status_emoji(s.status)}</td>"
            f"</tr>"
        )

    # Build failed details section
    failed_details_html = []
    for s in summaries:
        if s.failed_downloads or s.failed_deletions:
            failed_items = []
            for fr in s.failed_downloads:
                failed_items.append(
                    f"<li><code>{html.escape(fr.name)}</code> ({html.escape(fr.stage)}) - {html.escape(fr.error_message or '')}</li>"
                )
            for fr in s.failed_deletions:
                failed_items.append(
                    f"<li><code>{html.escape(fr.name)}</code> ({html.escape(fr.stage)}) - {html.escape(fr.error_message or '')}</li>"
                )
            if failed_items:
                failed_details_html.append(
                    f"<h3 style='color:#d32f2f;margin-top:20px;'>{html.escape(s.bip_name)}</h3>"
                    f"<ul style='color:#d32f2f;'>{''.join(failed_items)}</ul>"
                )

    failed_section = (
        "<h2 style='color:#d32f2f;margin-top:30px;'>Failed Details</h2>"
        + "\n".join(failed_details_html)
        if failed_details_html
        else ""
    )

    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th {{ background-color: #f2f2f2; padding: 10px; text-align: center; border-bottom: 2px solid #ddd; }}
            td {{ padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0; }}
            .status {{ font-size: 20px; }}
        </style>
    </head>
    <body>
        <h1>PaaS Data Extraction Script - Hourly Summary</h1>
        <p>Generated on: {now_str}</p>
        <table>
            <tr>
                <th>BIP</th>
                <th>Files Found</th>
                <th>Downloaded</th>
                <th>Deleted</th>
                <th>Failed</th>
                <th>Duration</th>
                <th>Status</th>
            </tr>
            {"".join(rows_html)}
        </table>
        {failed_section}
    </body>
    </html>
    """
    return html_body


def fetch_and_move(
    bip_name: str,
    sc_dct: dict[str, str],
    path_to_gcs_file: Path,
    email_sender: Sender,
) -> BIPSummary:
    """
    Fetches files via SFTP and moves them to GCS.
    Parameters:
        bip_name (str): Name of the BIP
        sc_dct (dict[str, str]): Secrets dictionary
        path_to_gcs_file (Path): Path to GCS credentials file
    Returns:
        BIPSummary: Summary of the run
    """

    raw_port = sc_dct.get("PORT", "22")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        error_msg = (
            f"Invalid PORT value for {bip_name}: '{raw_port}'. PORT must be an integer."
        )
        logging.error(error_msg)
        _safe_notify(
            email_sender,
            subject=" - Error Notification",
            body=error_msg,
        )
        return BIPSummary(
            bip_name=bip_name,
            files_found=0,
            downloaded=[],
            deleted=[],
            failed_downloads=[],
            failed_deletions=[],
            duration_s=0.0,
            status="failed",
        )

    # map to SFTPConfig dataclass
    sftp_conf = SFTPConfig(
        hostname=sc_dct.get("HOSTNAME", ""),
        username=sc_dct.get("USERNAME", ""),
        port=port,
        key_passphrase=sc_dct.get("PASSWORD", ""),
        path_to_key=sc_dct.get("PATH_TO_KEY", ""),
        local_path=sc_dct.get("LOCAL_PATH", "."),
        bucket_name=sc_dct.get("BUCKET_NAME", ""),
        path_to_gcs_credentials=str(path_to_gcs_file),
        target_file_type=sc_dct.get("TARGET_FILE_TYPE", ".csv"),
        remote_path=sc_dct.get("REMOTE_PATH", "/REPORTS"),
    )

    # initialize Fetcher class
    logging.info(f"> > > > > FETCHER task started for {bip_name} < < < < <")

    try:
        fetcher = Fetcher(
            config=sftp_conf,
            email_sender=email_sender,
            bip_name=bip_name,
        )
        return fetcher.fetch_files()

    except SystemExit as e:
        error_msg = f"SystemExit occurred while running Fetcher for {bip_name}: {e}"
        logging.error(error_msg)
        _safe_notify(
            email_sender,
            subject=" - SystemExit Notification",
            body=error_msg,
        )
        return BIPSummary(
            bip_name=bip_name,
            files_found=0,
            downloaded=[],
            deleted=[],
            failed_downloads=[],
            failed_deletions=[],
            duration_s=0.0,
            status="failed",
        )

    except Exception as e:
        error_msg = f"Error occurred while running Fetcher for {bip_name}: {e}"
        logging.error(error_msg)
        _safe_notify(
            email_sender,
            subject=" - Error Notification",
            body=error_msg,
        )
        return BIPSummary(
            bip_name=bip_name,
            files_found=0,
            downloaded=[],
            deleted=[],
            failed_downloads=[],
            failed_deletions=[],
            duration_s=0.0,
            status="failed",
        )


def main() -> None:
    # Start logging both in the terminal and the log file.
    init_logger()
    logging.info("Script started.")

    # init infisical client for fetching secrets
    infisical_config = init_infisical_client()
    client = infisical_config.client
    project_id = infisical_config.project_id
    project_slug = infisical_config.project_slug
    environment_slug = infisical_config.environment_slug

    try:
        # fetch secrets for email sender
        sc_email = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/SMTP",
        ).secrets
        sc_dct_email = {sc.secretKey: sc.secretValue for sc in sc_email}

        email_sender = init_sender(
            host="smtp.gmail.com",
            port=587,
            username=sc_dct_email.get("USERNAME", ""),
            password=sc_dct_email.get("PASSWORD", ""),
            from_addr=sc_dct_email.get("FROM_ADDR", ""),
            to_addrs=sc_dct_email.get("TO_ADDRS", "").split(","),
            use_tls=True,
            use_ssl=False,
            subject_prefix=sc_dct_email.get("SUBJECT_PREFIX", ""),
            app_name=sc_dct_email.get("APP_NAME", ""),
        )
    except Exception as e:
        logging.error(f"Error initializing email sender: {e}")
        sys.exit(1)

    # init path to gcs credentials file
    path_to_gcs_file = Path(__file__).resolve().parents[1] / "config" / "gcs.json"
    if not path_to_gcs_file.exists():
        logging.error(f"GCS credentials file not found at: {path_to_gcs_file}")
        sys.exit(1)

    summaries: list[BIPSummary] = []
    for bip_name, secret_path in BIP_JOBS:
        try:
            sc_dct = _secrets_dict_at_path(
                client,
                project_id=project_id,
                project_slug=project_slug,
                environment_slug=environment_slug,
                secret_path=secret_path,
            )
        except Exception as e:
            error_msg = f"Error fetching secrets for {bip_name}: {e}"
            logging.error(error_msg)
            _safe_notify(
                email_sender,
                subject=" - Error Notification",
                body=error_msg,
            )
            summaries.append(
                BIPSummary(
                    bip_name=bip_name,
                    files_found=0,
                    downloaded=[],
                    deleted=[],
                    failed_downloads=[],
                    failed_deletions=[],
                    duration_s=0.0,
                    status="failed",
                )
            )
            continue

        summary = fetch_and_move(
            bip_name=bip_name,
            sc_dct=sc_dct,
            path_to_gcs_file=path_to_gcs_file,
            email_sender=email_sender,
        )
        summaries.append(summary)

    # Send daily summary email
    try:
        html_body = _build_summary_html(summaries)
        text_body = _build_summary_text(summaries)
        email_sender.send(
            subject="Hourly Summary",
            body=text_body,
            html=html_body,
        )
        logging.info("Daily summary email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send daily summary email: {e}")


if __name__ == "__main__":
    main()
