import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from fetcher import Fetcher
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
    load_dotenv(env_path)

    if not env_path.exists():
        logging.error(f"Environment file not found at: {env_path}")
        return

    # initialize Fetcher instance for PRTPE_TEST
    logging.info("Starting fetcher for PRTPE_TEST...")
    prtpe_test = Fetcher(
        hostname=os.environ.get("SFTP_HOSTNAME_PRTPE_TEST", ""),
        username=os.environ.get("SFTP_USERNAME_PRTPE_TEST", ""),
        port=int(os.environ.get("SFTP_PORT_PRTPE_TEST", "")),
        password=os.environ.get("SFTP_PASSWORD_PRTPE_TEST", ""),
        path_to_key=os.environ.get("SFTP_PATH_TO_KEY_PRTPE_TEST", ""),
        local_path=os.environ.get("SFTP_LOCAL_PATH_PRTPE_TEST", "."),
        target_file_type=os.environ.get(
            "SFTP_TARGET_FILE_TYPE_PRTPE_TEST", ".csv"),
        remote_path=os.environ.get("SFTP_REMOTE_PATH_PRTPE_TEST", ".")
    )
    prtpe_test.fetch_files()

    # initialize Fetcher instance for PRTSO_TEST
    # logging.info("Starting fetcher for PRTSO_TEST...")
    # prtso_test = Fetcher(
    #     hostname=os.environ.get("SFTP_HOSTNAME_PRTSO_TEST", ""),
    #     username=os.environ.get("SFTP_USERNAME_PRTSO_TEST", ""),
    #     port=int(os.environ.get("SFTP_PORT_PRTSO_TEST", "")),
    #     password=os.environ.get("SFTP_PASSWORD_PRTSO_TEST", ""),
    #     path_to_key=os.environ.get("SFTP_PATH_TO_KEY_PRTSO_TEST", ""),
    #     local_path=os.environ.get("SFTP_LOCAL_PATH_PRTSO_TEST", "."),
    #     target_file_type=os.environ.get(
    #         "SFTP_TARGET_FILE_TYPE_PRTSO_TEST", ".csv"),
    #     remote_path=os.environ.get("SFTP_REMOTE_PATH_PRTSO_TEST", ".")
    # )
    # prtso_test.fetch_files()

    # initialize Fetcher instance for BIGE_TEST
    # logging.info("Starting fetcher for BIGE_TEST...")
    # bige_test = Fetcher(
    #     hostname=os.environ.get("SFTP_HOSTNAME_BIGE_TEST", ""),
    #     username=os.environ.get("SFTP_USERNAME_BIGE_TEST", ""),
    #     port=int(os.environ.get("SFTP_PORT_BIGE_TEST", "")),
    #     password=os.environ.get("SFTP_PASSWORD_BIGE_TEST", ""),
    #     path_to_key=os.environ.get("SFTP_PATH_TO_KEY_BIGE_TEST", ""),
    #     local_path=os.environ.get("SFTP_LOCAL_PATH_BIGE_TEST", "."),
    #     target_file_type=os.environ.get(
    #         "SFTP_TARGET_FILE_TYPE_BIGE_TEST", ".csv"),
    #     remote_path=os.environ.get("SFTP_REMOTE_PATH_BIGE_TEST", ".")
    # )
    # bige_test.fetch_files()

    # initialize Fetcher instance for SOLID_TEST
    # logging.info("Starting fetcher for SOLID_TEST...")
    # solid_test = Fetcher(
    #     hostname=os.environ.get("SFTP_HOSTNAME_SOLID_TEST", ""),
    #     username=os.environ.get("SFTP_USERNAME_SOLID_TEST", ""),
    #     port=int(os.environ.get("SFTP_PORT_SOLID_TEST", "")),
    #     password=os.environ.get("SFTP_PASSWORD_SOLID_TEST", ""),
    #     path_to_key=os.environ.get("SFTP_PATH_TO_KEY_SOLID_TEST", ""),
    #     local_path=os.environ.get("SFTP_LOCAL_PATH_SOLID_TEST", "."),
    #     target_file_type=os.environ.get(
    #         "SFTP_TARGET_FILE_TYPE_SOLID_TEST", ".csv"),
    #     remote_path=os.environ.get("SFTP_REMOTE_PATH_SOLID_TEST", ".")
    # )
    # solid_test.fetch_files()

    # initialize Mover class
    logging.info("Starting mover script...")
    path_to_gcs_file = Path(__file__).parents[1] / "config" / "gcs.json"
    mover = Mover(
        working_dir=Path(os.environ.get("SFTP_LOCAL_PATH", "")),
        sent_dir=Path(os.environ.get("SENT_ITEMS_PATH", "")),
        path_to_gcs_credentials=str(path_to_gcs_file)
    )

    # upload files to GCS and move to 'sent' folder
    mover.start()


if __name__ == "__main__":
    main()
