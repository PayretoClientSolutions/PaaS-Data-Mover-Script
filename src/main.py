import html
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

from fetcher import Fetcher
from models import BIPSummary, EmailConfig, SFTPConfig
from sender import Sender

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
BIP_JOBS = ["PRTPE", "PRTSO", "SOLID", "BIGE"]


def init_logger() -> None:
    """Append logs to app.log and echo them to the console."""
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
    Build the email sender from SMTP settings.

    The returned sender is configured only; it does not open an SMTP connection
    until an email is sent.

    Args:
        host: SMTP server host.
        port: SMTP server port.
        username: SMTP username.
        password: SMTP password.
        from_addr: Email address used as the From header.
        to_addrs: Recipient email addresses.
        use_tls: Whether to upgrade the connection with STARTTLS.
        use_ssl: Whether to use implicit TLS from connection start.
        subject_prefix: Prefix added to outbound email subjects.
        app_name: Application name used in generated exception subjects.

    Returns:
        Configured Sender instance.
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


def group_settings(
    settings: dict[str, str], prefix: str, required: tuple[str, ...]
) -> dict[str, str]:
    group = {
        key.removeprefix(prefix + "_"): value
        for key, value in settings.items()
        if key.startswith(prefix + "_") and value != ""
    }
    missing = [f"{prefix}_{key}" for key in required if not group.get(key, "").strip()]
    if missing:
        raise ValueError("Missing required settings: " + ", ".join(missing))
    return group


def _now_str() -> str:
    """Return the current local timestamp for logs and email subjects."""
    return datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _safe_notify(email_sender: Sender, *, subject: str, body: str) -> None:
    """Send an email notification without propagating SMTP failures."""
    try:
        email_sender.send(subject=subject, body=body)
    except Exception as notify_error:  # noqa: BLE001 - notifications must not abort work
        logger.error(f"Failed to send notification email: {notify_error}")


def _status_emoji(status: str) -> str:
    return {
        "success": "&#x2705;",
        "partial": "&#x26A0;",
        "failed": "&#x274C;",
        "no_files": "&#x26AA;",
    }.get(status, "&#x2753;")


def _build_summary_text(summaries: list[BIPSummary]) -> str:
    """Build the plain-text fallback body for the summary email."""
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
    """Build the HTML body for the summary email."""
    now_str = _now_str()
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
    Run one BIP transfer from SFTP to GCS using its configured credentials.

    Invalid configuration and Fetcher failures are logged, reported by email,
    and converted into a failed BIPSummary instead of aborting the full job run.

    Args:
        bip_name: Name used in logs, notifications, and summaries.
        sc_dct: Settings for this BIP.
        path_to_gcs_file: Local GCS service account credentials file.
        email_sender: Sender used for failure notifications.

    Returns:
        Summary of the BIP transfer attempt.
    """

    raw_port = sc_dct.get("PORT", "22")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        error_msg = f"Invalid {bip_name}_PORT. PORT must be an integer."
        logger.error(error_msg)
        _safe_notify(
            email_sender,
            subject=f"[{_now_str()}] [{bip_name}] Port validation error",
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
    logger.info(f"> > > > > FETCHER task started for {bip_name} < < < < <")

    try:
        fetcher = Fetcher(
            config=sftp_conf,
            email_sender=email_sender,
            bip_name=bip_name,
        )
        return fetcher.fetch_files()

    except SystemExit as e:
        error_msg = f"SystemExit occurred while running Fetcher for {bip_name}: {e}"
        logger.error(error_msg)
        _safe_notify(
            email_sender,
            subject=f"[{_now_str()}] [{bip_name}] SystemExit occurred",
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

    except Exception as e:  # noqa: BLE001 - isolate failures to one BIP
        error_msg = f"Error occurred while running Fetcher for {bip_name}: {e}"
        logger.error(error_msg)
        _safe_notify(
            email_sender,
            subject=f"[{_now_str()}] [{bip_name}] Fetcher error",
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
    """Run all configured BIP jobs and send the hourly summary email."""

    # Start logging both in the terminal and the log file.
    init_logger()
    logger.info("Script started.")

    env_path = CONFIG_DIR / ".env"
    try:
        with env_path.open(encoding="utf-8") as stream:
            settings = {
                key: value
                for key, value in dotenv_values(
                    stream=stream, interpolate=False
                ).items()
                if value is not None
            }
        sc_dct_email = group_settings(
            settings, "SMTP", ("USERNAME", "PASSWORD", "FROM_ADDR", "TO_ADDRS")
        )
        recipients = [
            addr.strip() for addr in sc_dct_email["TO_ADDRS"].split(",") if addr.strip()
        ]
        if not recipients:
            raise ValueError("SMTP_TO_ADDRS requires at least one recipient")
        email_sender = init_sender(
            host="smtp.gmail.com",
            port=587,
            username=sc_dct_email.get("USERNAME", ""),
            password=sc_dct_email.get("PASSWORD", ""),
            from_addr=sc_dct_email.get("FROM_ADDR", ""),
            to_addrs=recipients,
            use_tls=True,
            use_ssl=False,
            subject_prefix=sc_dct_email.get("SUBJECT_PREFIX", ""),
            app_name=sc_dct_email.get("APP_NAME", ""),
        )
    except Exception as e:  # noqa: BLE001 - initialization failures terminate cleanly
        logger.error(f"Error initializing email sender: {e}")
        sys.exit(1)

    # init path to gcs credentials file
    path_to_gcs_file = CONFIG_DIR / "gcs.json"
    if not path_to_gcs_file.exists():
        logger.error(f"GCS credentials file not found at: {path_to_gcs_file}")
        sys.exit(1)

    summaries: list[BIPSummary] = []
    for bip_name in BIP_JOBS:
        try:
            sc_dct = group_settings(
                settings,
                bip_name,
                ("HOSTNAME", "USERNAME", "PATH_TO_KEY", "BUCKET_NAME"),
            )
        except ValueError as e:
            error_msg = f"Invalid configuration for {bip_name}: {e}"
            logger.error(error_msg)
            _safe_notify(
                email_sender,
                subject=f"[{_now_str()}] [{bip_name}] Configuration error",
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
            subject=f"[{_now_str()}] Hourly Summary",
            body=text_body,
            html=html_body,
        )
        logger.info("Daily summary email sent successfully.")
    except Exception as e:  # noqa: BLE001 - summary email failure must not mask results
        logger.error(f"Failed to send daily summary email: {e}")


if __name__ == "__main__":
    main()
