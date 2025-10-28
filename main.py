import logging
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage

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

    # take environment variables
    load_dotenv()

    # initialize Mover class
    mover = Mover(
        working_dir=Path(os.environ.get("ACI_USER_PATH", "/home/aci/uploads")),
        sent_dir=Path(os.environ.get("SENT_ITEMS_PATH", "/home/aci/sent")),
        path_to_gcs_credentials=str(Path.cwd() / 'gcs.json')
    )

    mover.start()


if __name__ == "__main__":
    main()
