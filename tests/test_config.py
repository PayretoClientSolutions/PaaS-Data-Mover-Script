import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import main
from models import BIPSummary


class LocalConfigTest(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.directory = Path(directory)
        self.enterContext(patch.object(main, "CONFIG_DIR", self.directory))
        self.enterContext(patch.object(main, "init_logger"))
        self.sender = self.enterContext(patch.object(main, "Sender"))
        self.fetcher = self.enterContext(patch.object(main, "Fetcher"))
        self.fetcher.return_value.fetch_files.return_value = BIPSummary(
            "PRTSO", 0, [], [], [], [], 0.0, "no_files"
        )
        self.env = self.directory / ".env"
        (self.directory / "gcs.json").touch()

    def test_template_loads_isolated_credentials_and_skips_incomplete_job(self):
        template = (ROOT / "config/.env.example").read_text()
        values = {
            "SMTP_USERNAME": "mailer",
            "SMTP_PASSWORD": "literal${VALUE}",
            "SMTP_FROM_ADDR": "from@example.test",
            "SMTP_TO_ADDRS": "a@example.test, b@example.test",
        }
        for job in main.BIP_JOBS:
            values.update(
                {
                    f"{job}_HOSTNAME": job.lower(),
                    f"{job}_USERNAME": job + "-user",
                    f"{job}_PATH_TO_KEY": "/" + job,
                    f"{job}_BUCKET_NAME": job.lower() + "-bucket",
                }
            )
        del values["PRTPE_HOSTNAME"]
        values.update(PRTSO_PASSWORD="partner-passphrase", BIGE_PORT="2222")
        lines = []
        for line in template.splitlines():
            key = line.partition("=")[0]
            lines.append(f"{key}={values[key]}" if key in values else line)
        self.env.write_text(
            "\n".join(line for line in lines if line != "PRTSO_PORT=22")
        )
        main.main()

        mail = self.sender.call_args.kwargs["config"]
        self.assertEqual(mail.password, "literal${VALUE}")
        self.assertEqual(mail.to_addrs, ["a@example.test", "b@example.test"])
        calls = [call.kwargs for call in self.fetcher.call_args_list]
        self.assertEqual([c["bip_name"] for c in calls], ["PRTSO", "SOLID", "BIGE"])
        for call in calls:
            self.assertEqual(call["config"].hostname, call["bip_name"].lower())
        self.assertEqual(calls[0]["config"].port, 22)
        self.assertEqual(calls[0]["config"].key_passphrase, "partner-passphrase")
        self.assertEqual(calls[-1]["config"].port, 2222)
        notices = self.sender.return_value.send.call_args_list
        self.assertIn("PRTPE_HOSTNAME", notices[0].kwargs["body"])
        self.assertIn("Hourly Summary", notices[-1].kwargs["subject"])

    def test_missing_smtp_credentials_stop_before_transfers(self):
        self.env.write_text("SMTP_USERNAME=mailer\n")
        with self.assertRaises(SystemExit), self.assertLogs(level="ERROR") as logs:
            main.main()
        self.assertIn("SMTP_PASSWORD", logs.output[0])
        self.fetcher.assert_not_called()
