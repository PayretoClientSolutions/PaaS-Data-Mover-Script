import logging
import os
import shutil
import sys
from pathlib import Path

from google.cloud import storage


def init_logger() -> None:
    """
    Initializes the logger for the whole script
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log", mode="a"),  # logs to a file
            logging.StreamHandler()  # logs to console
        ]
    )


def get_files_list(working_dir: Path) -> list[Path]:
    """
    Returns the list of file paths from the 'incoming' directory in the current working directory.
    """
    incoming_dir = working_dir / 'incoming'
    logging.info(f"Looking for files in directory: {incoming_dir}")

    files_list = [f for f in incoming_dir.iterdir() if f.is_file()]
    return files_list


def move_to_sent_folder(file: Path, working_dir: Path) -> None:
    """
    Move the processed file to the 'sent' directory.
    The 'sent' directory must exist before moving files.
    """
    logging.info(f"Moving file '{file.name}' to the 'sent' directory.")
    destination = working_dir / 'sent' / file.name

    # Todo: add validation to check if file already exists in the destination
    shutil.move(file, destination)


def validate_directories(working_dir: Path) -> None:
    """
    Check that required directories exist, exit if not.
    """
    required_dirs = [
        working_dir / 'incoming',
        working_dir / 'sent'
    ]
    for directory in required_dirs:
        logging.info(f"Checking if directory exists: {directory}")
        if not directory.exists():
            error_msg = f"Required directory '{directory}' does not exist. Exiting..."
            logging.fatal(error_msg)
            sys.exit(1)


def upload_file_to_gcs(file_path: Path) -> bool:
    """
    Uploads a file to Google Cloud Storage. Returns True if upload is successful, False otherwise.
    The GCS credentials file renamed to 'gcs.json' must be located in the current working directory.
    """
    _bucket_name_: str = 'aci_raw'
    client = storage.Client()

    # bucket instance
    bucket = client.get_bucket(_bucket_name_)

    # upload the file
    logging.info(
        f"Uploading file '{file_path.name}' to GCS bucket '{_bucket_name_}'"
    )

    try:
        blob = bucket.blob(file_path.name)
        blob.upload_from_filename(filename=str(file_path))
        return True

    except Exception as e:
        logging.error(f"Failed to upload file '{file_path.name}' to GCS: {e}")
        return False


def main() -> None:
    """
    Step 1. Get the list of files
    Step 2. Iterate through the list
        Step 2.5 Upload the file to the data lake
        Step 2.6 Move the file to 'sent' directory
    """
    # Start logging both in the terminal and the log file
    init_logger()

    # init Path and set env variable for GCS credentials
    cwd = Path.cwd()
    working_dir = Path.home()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cwd / 'gcs.json')

    # check if required directories exist
    validate_directories(working_dir)

    file_paths = get_files_list(working_dir)

    # Stop processing if the list is empty
    if not file_paths:
        logging.info("No file(s) found in 'incoming' directory. Exiting...")
        return

    # Iterate through each file path for processing
    for file in file_paths:
        if upload_file_to_gcs(file):
            move_to_sent_folder(file, working_dir)


if __name__ == "__main__":
    main()
