import logging
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage


class Mover:
    def __init__(self, working_dir: Path, sent_dir: Path, path_to_gcs_credentials: str) -> None:
        self.working_dir = working_dir
        self.sent_dir = sent_dir
        self.path_to_gcs_credentials = path_to_gcs_credentials

        # validate required directories exist
        self._validate_directories(self.working_dir)
        self._validate_directories(self.sent_dir)

    def _get_files_list(self) -> list[Path]:
        """
        Returns the list of file paths from the 'uploads' directory in the current working directory.
        Exits the script if the directory is empty.
        """
        incoming_dir = self.working_dir
        logging.info(f"Looking for files in directory: {incoming_dir}")

        files_list = [f for f in incoming_dir.iterdir() if f.is_file()]
        if not files_list:
            logging.fatal("Incoming directory is empty. Exiting...")
            sys.exit(1)

        logging.info(f"Found {len(files_list)} file(s) in incoming directory.")
        return files_list

    def _move_to_sent_folder(self, file: Path) -> None:
        """
        Move the processed file to the 'sent' directory.
        The 'sent' directory must exist before moving files.
        """
        logging.info(f"Moving file '{file.name}' to '{self.sent_dir}'.")
        destination = self.sent_dir / file.name

        # Todo: add validation to check if file already exists in the destination
        shutil.move(file, destination)

    def _validate_directories(self, dir: Path) -> None:
        """
        Check that the required directory exists, exit if not.
        """
        logging.info(f"Checking if directory exists: {dir}")
        if not dir.exists():
            logging.fatal(
                f"Required directory '{dir}' does not exist. Exiting..."
            )
            sys.exit(1)

    def _upload_file_to_gcs(self, file_path: Path) -> bool:
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
            logging.error(
                f"Failed to upload file '{file_path.name}' to GCS: {e}")
            return False

    def start(self) -> None:
        # Fetch the list of files to be processed.
        files_list = self._get_files_list()

        # init google GCS credentials
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.path_to_gcs_credentials

        # start timer to measure performance
        start = time.perf_counter()

        # Iterate through each file path for processing.
        # If the upload fails, do not move the file to 'sent' directory.
        uploaded_files_count = 0
        for file in files_list:
            if self._upload_file_to_gcs(file):
                uploaded_files_count += 1
                self._move_to_sent_folder(file)

        # end timer then log duration
        end = time.perf_counter()
        final_msg = f"Uploaded {uploaded_files_count} out of {len(files_list)} file(s) successfully for {end - start:.6f} seconds."
        logging.info(final_msg)
