import importlib
import io
import logging
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main
from fetcher import Fetcher
from models import BIPSummary, EmailConfig, FileResult, SFTPConfig
from sender import Sender

fetcher_module = importlib.import_module("fetcher.fetcher")
sender_module = importlib.import_module("sender.sender")


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 11, 14, 5, 9)


class BehaviorRegressionTests(unittest.TestCase):
    def test_public_model_exports_are_unchanged(self):
        self.assertIsNotNone(BIPSummary)
        self.assertIsNotNone(EmailConfig)
        self.assertIsNotNone(FileResult)
        self.assertIsNotNone(SFTPConfig)

    def test_timestamps_keep_local_wall_clock_format(self):
        with (
            patch.object(main, "datetime", FixedDateTime),
            patch.object(fetcher_module, "datetime", FixedDateTime),
        ):
            self.assertEqual(main._now_str(), "2026-08-11 14:05:09")
            self.assertEqual(Fetcher._now_str(), "2026-08-11 14:05:09")
            self.assertIn(
                "Generated on: 2026-08-11 14:05:09",
                main._build_summary_html([]),
            )

    def test_named_logger_preserves_configured_output_text(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        root_logger = logging.getLogger()
        previous_handlers = root_logger.handlers[:]
        previous_level = root_logger.level

        try:
            root_logger.handlers = [handler]
            root_logger.setLevel(logging.INFO)
            main.logger.info("Script started.")
        finally:
            root_logger.handlers = previous_handlers
            root_logger.setLevel(previous_level)

        self.assertEqual(stream.getvalue(), "INFO - Script started.\n")

    def test_notification_failure_is_logged_and_suppressed(self):
        email_sender = MagicMock()
        email_sender.send.side_effect = RuntimeError("smtp down")

        with self.assertLogs(main.logger, level="ERROR") as captured:
            main._safe_notify(email_sender, subject="subject", body="body")

        self.assertEqual(
            captured.output,
            ["ERROR:main:Failed to send notification email: smtp down"],
        )

    def test_upload_failure_retains_file_and_returns_false(self):
        fetcher = Fetcher.__new__(Fetcher)
        fetcher.email_sender = MagicMock()
        fetcher.bip_name = "TEST"
        bucket = MagicMock()
        bucket.blob.return_value.upload_from_filename.side_effect = RuntimeError(
            "upload failed"
        )

        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "report.csv"
            file_path.write_text("data", encoding="utf-8")

            with (
                patch.object(Fetcher, "_now_str", return_value="2026-08-11 14:05:09"),
                self.assertLogs(fetcher_module.logger, level="ERROR"),
            ):
                result = fetcher._upload_file_to_gcs(file_path, bucket)

            self.assertFalse(result)
            self.assertTrue(file_path.exists())

        fetcher.email_sender.send.assert_called_once_with(
            subject="[2026-08-11 14:05:09] [TEST] Upload failed",
            body="Failed to upload file report.csv: upload failed",
        )

    def test_fetcher_failure_still_returns_failed_summary(self):
        email_sender = MagicMock()

        with (
            patch.object(main, "Fetcher", side_effect=RuntimeError("fetch failed")),
            patch.object(main, "_now_str", return_value="2026-08-11 14:05:09"),
            self.assertLogs(main.logger, level="ERROR"),
        ):
            summary = main.fetch_and_move(
                bip_name="TEST",
                sc_dct={},
                path_to_gcs_file=Path("config/gcs.json"),
                email_sender=email_sender,
            )

        self.assertEqual(summary.status, "failed")
        self.assertEqual(summary.bip_name, "TEST")
        self.assertEqual(summary.files_found, 0)
        email_sender.send.assert_called_once_with(
            subject="[2026-08-11 14:05:09] [TEST] Fetcher error",
            body="Error occurred while running Fetcher for TEST: fetch failed",
        )

    def test_unreadable_attachment_is_skipped_before_sending(self):
        sender = Sender(
            EmailConfig(
                host="smtp.example.com",
                port=587,
                from_addr="from@example.com",
                to_addrs=["to@example.com"],
            )
        )
        connection = MagicMock()
        server = connection.__enter__.return_value

        with (
            patch.object(sender, "_connect", return_value=connection),
            self.assertLogs(sender_module.logger, level="WARNING") as captured,
        ):
            sender.send(
                subject="Subject",
                body="Body",
                attachments=[Path("missing-attachment.txt")],
            )

        self.assertIn(
            "Failed to attach file missing-attachment.txt", captured.output[0]
        )
        server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
