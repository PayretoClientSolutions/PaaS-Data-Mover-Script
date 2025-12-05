import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient

from fetcher import Fetcher
from models import SFTPConfig
from models.models import MoverConfig
from mover import Mover


def init_logger() -> None:
    """
    Initializes the logger for the whole script
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log", mode="a"),  # Logs to a file.
            logging.StreamHandler()  # Logs to console.
        ]
    )


def main() -> None:
    # Start logging both in the terminal and the log file.
    init_logger()

    # read environment variables from .env file
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
    logging.info(f"Loading environment variables from: {env_path}")
    if not env_path.exists():
        logging.error(f"Environment file not found at: {env_path}")
        return

    load_dotenv(env_path)

    try:
        logging.info("Fetching secrets from Infisical...")

        client = InfisicalSDKClient(host="https://eu.infisical.com")
        client.auth.token_auth.login(
            token=os.environ.get("INFISCAL_TOKEN", ""))

        secrets = client.secrets.list_secrets(
            project_id="3ed6ea7a-049a-4453-8510-acb86fe0270a",
            project_slug="paa-s-sftp-htwm",
            environment_slug=os.environ.get("INFISCAL_ENVIRONMENT", "dev"),
            secret_path="/"
        )

        # convert secrets to a dictionary
        secrets_dict = {
            secret.secretKey: secret.secretValue for secret in secrets.secrets}

        # map to SFTPConfig dataclass
        prtpe_test_sftp_config = SFTPConfig(
            hostname=secrets_dict.get("SFTP_HOSTNAME_PRTPE_TEST", ""),
            username=secrets_dict.get("SFTP_USERNAME_PRTPE_TEST", ""),
            port=int(secrets_dict.get("SFTP_PORT_PRTPE_TEST", "22")),
            password=secrets_dict.get("SFTP_PASSWORD_PRTPE_TEST", ""),
            path_to_key=secrets_dict.get("SFTP_PATH_TO_KEY_PRTPE_TEST", ""),
            local_path=secrets_dict.get("SFTP_LOCAL_PATH_PRTPE_TEST", "."),
            target_file_type=secrets_dict.get(
                "SFTP_TARGET_FILE_TYPE_PRTPE_TEST", ".csv"),
            remote_path=secrets_dict.get(
                "SFTP_REMOTE_PATH_PRTPE_TEST", "/REPORTS")
        )

    except Exception as e:
        logging.error(f"Error fetching secrets from Infisical: {e}")
        return

    # initialize Fetcher instance for PRTPE_TEST
    logging.info("Starting fetcher for PRTPE_TEST...")
    prtpe_test = Fetcher(config=prtpe_test_sftp_config)
    prtpe_test.fetch_files()

    # initialize Mover class
    logging.info("Moving items from PRTPE_TEST...")
    path_to_gcs_file = Path(__file__).parents[1] / "config" / "gcs.json"
    mover_config = MoverConfig(
        working_dir=Path(prtpe_test_sftp_config.local_path),
        sent_dir=Path(secrets_dict.get("SENT_ITEMS_PATH_PRTPE_TEST", "")),
        path_to_gcs_credentials=str(path_to_gcs_file)
    )
    mover = Mover(mover_config)
    mover.start()


if __name__ == "__main__":
    main()
