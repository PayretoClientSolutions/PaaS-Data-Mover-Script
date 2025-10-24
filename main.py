import logging
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage


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


def get_files_list(working_dir: Path) -> list[Path]:
    """
    Returns the list of file paths from the 'uploads' directory in the current working directory.
    Exits the script if the directory is empty.
    """
    incoming_dir = working_dir
    logging.info(f"Looking for files in directory: {incoming_dir}")

    files_list = [f for f in incoming_dir.iterdir() if f.is_file()]
    if not files_list:
        logging.fatal("Incoming directory is empty. Exiting...")
        sys.exit(1)

    logging.info(f"Found {len(files_list)} file(s) in incoming directory.")
    return files_list


def move_to_sent_folder(file: Path, sent_dir: Path) -> None:
    """
    Move the processed file to the 'sent' directory.
    The 'sent' directory must exist before moving files.
    """
    logging.info(f"Moving file '{file.name}' to the 'sent' directory.")
    destination = sent_dir / file.name

    # Todo: add validation to check if file already exists in the destination
    shutil.move(file, destination)


def validate_directories(dir: Path) -> None:
    """
    Check that the required directory exists, exit if not.
    """
    logging.info(f"Checking if directory exists: {dir}")
    if not dir.exists():
        logging.fatal(
            f"Required directory '{dir}' does not exist. Exiting..."
        )
        sys.exit(1)


def upload_file_to_gcs(file_path: Path) -> bool:
    """
    Uploads a file to Google Cloud Storage.\n
    Returns True if upload is successful, False otherwise.\n
    This function assumes that the GCS bucket 'aci_raw' already exists.
    The GCS credentials file renamed to 'gcs.json' must be located in the current working directory.
    """

    # Initialize GCS client.
    logging.info("Initializing Google Cloud Storage client.")
    client = storage.Client()

    # Initialize Bucket instance.
    bucket_name: str = os.getenv("BUCKET_NAME", "aci_raw")
    try:
        bucket = client.get_bucket(bucket_name)
    except Exception as e:
        logging.fatal(f"Could not access GCS bucket '{bucket_name}': {e}")
        sys.exit(1)

    # Upload the file.
    try:
        logging.info(
            f"Uploading file '{file_path.name}' to GCS bucket '{bucket_name}'"
        )
        blob = bucket.blob(file_path.name)
        blob.upload_from_filename(filename=str(file_path))
        return True

    except Exception as e:
        logging.error(f"Failed to upload file '{file_path.name}' to GCS: {e}")
        return False


def main() -> None:
    """
    Step 1. Get the list of files.\n
    Step 2. Iterate through the list.\n
    Step 2.5 Upload the file to the data lake.\n
    Step 2.6 Move the uploaded file to 'sent' directory.\n
    """

    # Start logging both in the terminal and the log file.
    init_logger()
    load_dotenv()  # take environment variables

    # Init Path and set env variable for GCS credentials.
    working_dir = Path(os.environ.get("ACI_USER_PATH", "/home/aci/uploads"))
    sent_dir = Path(os.environ.get("SENT_ITEMS_PATH", "/home/aci/sent"))

    # validate required directories exist
    validate_directories(working_dir)
    validate_directories(sent_dir)

    # Fetch the list of files to be processed.
    files_list = get_files_list(working_dir)

    # init google GCS credentials
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path.cwd() / 'gcs.json')

    # start timer to measure performance
    start = time.perf_counter()

    # Iterate through each file path for processing.
    # If the upload fails, do not move the file to 'sent' directory.
    uploaded_files_count = 0
    for file in files_list:
        if upload_file_to_gcs(file):
            uploaded_files_count += 1
            move_to_sent_folder(file, sent_dir)

    # end timer then log duration
    end = time.perf_counter()
    final_msg = f"Uploaded {uploaded_files_count} out of {len(files_list)} file(s) successfully for {end - start:.6f} seconds."
    logging.info(final_msg)


if __name__ == "__main__":
    main()
