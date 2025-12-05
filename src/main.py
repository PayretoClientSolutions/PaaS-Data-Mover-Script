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

    # init path to gcs credentials file
    path_to_gcs_file = Path(__file__).parents[1] / "config" / "gcs.json"

    try:
        logging.info("Fetching secrets from Infisical...")
        client = InfisicalSDKClient(
            host="https://eu.infisical.com",
            token=os.environ.get("INFISCAL_TOKEN", "")
        )

        # fetch secrets for PRTPE_TEST
        sc_prtpe_test = client.secrets.list_secrets(
            project_id="3ed6ea7a-049a-4453-8510-acb86fe0270a",
            project_slug="paa-s-sftp-htwm",
            environment_slug=os.environ.get("INFISCAL_ENVIRONMENT", "dev"),
            secret_path="/prtpe_test"
        ).secrets

        sc_dct_prtpe_test = {
            sc.secretKey: sc.secretValue for sc in sc_prtpe_test}

        bn_prtpe_test = sc_dct_prtpe_test.get("BUCKET_NAME", "")
        sd_prtpe_test = sc_dct_prtpe_test.get("SENT_ITEMS_PATH", "")

    except Exception as e:
        logging.error(f"Error fetching secrets from Infisical: {e}")
        return

    ### PRTPE TEST ###

    # map to SFTPConfig dataclass
    sftp_conf_prtpe_test = SFTPConfig(
        hostname=sc_dct_prtpe_test.get("HOSTNAME", ""),
        username=sc_dct_prtpe_test.get("USERNAME", ""),
        port=int(sc_dct_prtpe_test.get("PORT", "22")),
        password=sc_dct_prtpe_test.get("PASSWORD", ""),
        path_to_key=sc_dct_prtpe_test.get("PATH_TO_KEY", ""),
        local_path=sc_dct_prtpe_test.get("LOCAL_PATH", ".")
    )

    # initialize Fetcher instance for PRTPE_TEST
    logging.info("Starting FETCHER for PRTPE_TEST...")
    Fetcher(config=sftp_conf_prtpe_test).fetch_files()

    # initialize Mover class
    logging.info("Starting MOVER for PRTPE_TEST...")
    mover_config = MoverConfig(
        working_dir=Path(sftp_conf_prtpe_test.local_path),
        sent_dir=Path(sd_prtpe_test),
        path_to_gcs_credentials=str(path_to_gcs_file),
        bucket_name=bn_prtpe_test
    )
    Mover(mover_config).start()


if __name__ == "__main__":
    main()
