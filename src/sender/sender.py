import logging
import mimetypes
import smtplib
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

from models import EmailConfig

logger = logging.getLogger(__name__)


class Sender:
    """
    SMTP email sender for error notifications and general messages.

    Usage example:
        from models import EmailConfig
        from sender import Sender

        cfg = EmailConfig(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            from_addr="noreply@example.com",
            to_addrs=["ops@example.com"],
            use_tls=True,
            subject_prefix="[PaaS-Data-Mover]",
            app_name="PaaS-Data-Mover",
        )
        Sender(cfg).send_exception(e, context={"bip": bip_name})
    """

    def __init__(self, config: EmailConfig):
        self.config = config

    def _connect(self) -> smtplib.SMTP:
        if self.config.use_ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                self.config.host, self.config.port, timeout=30)
        else:
            server = smtplib.SMTP(
                self.config.host, self.config.port, timeout=30)
        server.ehlo()
        if not self.config.use_ssl and self.config.use_tls:
            try:
                server.starttls()
                server.ehlo()
            except Exception as e:
                logger.warning(f"STARTTLS failed or not supported: {e}")
        if self.config.username and self.config.password:
            server.login(self.config.username, self.config.password)
        return server

    def _format_subject(self, subject: str) -> str:
        prefix = (self.config.subject_prefix or "").strip()
        if prefix and not subject.startswith(prefix):
            return f"{prefix} {subject}"
        return subject

    def _ensure_recipients(self, to_addrs: Optional[Iterable[str]]) -> list[str]:
        recipients = list(to_addrs or self.config.to_addrs)
        if not recipients:
            raise ValueError("No recipients provided (to_addrs is empty).")
        return recipients

    def send(
        self,
        subject: str,
        body: str,
        html: Optional[str] = None,
        to_addrs: Optional[Iterable[str]] = None,
        attachments: Optional[Iterable[Path]] = None,
    ) -> None:
        """
        Send an email message.

        Args:
            subject: Email subject line.
            body: Plain text body content.
            html: Optional HTML body alternative.
            to_addrs: Optional override for recipients; defaults to config.to_addrs.
            attachments: Optional iterable of file Paths to attach.
        """
        recipients = self._ensure_recipients(to_addrs)

        msg = EmailMessage()
        msg["From"] = self.config.from_addr
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = self._format_subject(subject)

        if html:
            msg.set_content(body)
            msg.add_alternative(html, subtype="html")
        else:
            msg.set_content(body)

        for path in attachments or []:
            try:
                ctype, encoding = mimetypes.guess_type(str(path))
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                with open(path, "rb") as fp:
                    data = fp.read()
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=Path(path).name
                )
            except Exception as e:
                logger.warning(f"Failed to attach file {path}: {e}")

        try:
            with self._connect() as server:
                server.send_message(msg)
                logger.info(f"Email sent to {recipients}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

    def send_exception(
        self,
        exc: BaseException,
        context: Optional[dict] = None,
        to_addrs: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Convenience method to send a formatted exception email with traceback.

        Args:
            exc: The exception instance to report.
            context: Optional dictionary with extra context to include.
            to_addrs: Optional override for recipients.
        """
        app = self.config.app_name or "Application"
        exc_name = type(exc).__name__
        subject = f"{app} error: {exc_name}"
        tb = traceback.format_exc() or "(no traceback available)"

        lines = [
            f"An exception occurred in {app}:",
            "",
            f"Type: {exc_name}",
            f"Message: {exc}",
            "",
            "Traceback:",
            tb,
        ]

        if context:
            lines.extend(["", "Context:"])
            for k, v in context.items():
                lines.append(f"- {k}: {v}")

        body = "\n".join(lines)
        self.send(subject=subject, body=body, to_addrs=to_addrs)
