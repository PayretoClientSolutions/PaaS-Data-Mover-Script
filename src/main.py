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

    # initialize Fetcher class
    logging.info("Starting fetcher script...")
    fetcher = Fetcher(
        hostname=os.environ.get("SFTP_HOSTNAME", ""),
        username=os.environ.get("SFTP_USERNAME", ""),
        port=int(os.environ.get("SFTP_PORT", "")),
        password=os.environ.get("SFTP_PASSWORD", ""),
        path_to_key=os.environ.get("SFTP_PATH_TO_KEY", ""),
        local_path=os.environ.get("SFTP_LOCAL_PATH", "."),
        target_file_type=os.environ.get("SFTP_TARGET_FILE_TYPE", ".csv"),
        remote_path=os.environ.get("SFTP_REMOTE_PATH", ".")
    )
    fetcher.fetch_files()

    # initialize Mover class
    # logging.info("Starting mover script...")
    # mover = Mover(
    #     working_dir=Path(os.environ.get("ACI_USER_PATH", "/home/aci/uploads")),
    #     sent_dir=Path(os.environ.get("SENT_ITEMS_PATH", "/home/aci/sent")),
    #     path_to_gcs_credentials=str(
    #         Path(__file__).parents[1] / "config" / "gcs.json")
    # )
    # mover.start()


if __name__ == "__main__":
    main()
