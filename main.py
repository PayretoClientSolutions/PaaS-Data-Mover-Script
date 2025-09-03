import logging
from pathlib import Path
import shutil

def init_logger():
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

def get_files_list(cwd: Path) -> list[Path]:
    """
    Returns the list of file paths from the 'received' directory in the current working directory.
    """

    received_dir = cwd / 'received'
    logging.info(f"Looking for files in directory: {received_dir}")

    files_list = [f for f in received_dir.iterdir() if f.is_file()]
    return files_list

def move_to_sent_folder(file: Path, cwd: Path):
    """
    Move the processed file to the 'sent' directory.
    The 'sent' directory must exist before moving files.
    """
    logging.info(f"Moving file {file.name} to 'sent' directory.")
    destination = cwd / 'sent' / file.name
    shutil.move(file, destination)


def main():
    """
    Step 1. Get the list of files
    Step 2. Iterate through the list
        Step 2.5 Upload file to the data lake
        Step 2.6 Move file to 'sent' directory
    """

    # Start logging both in the terminal and the log file
    init_logger()

    # Iterate through each file path for processing
    cwd = Path.cwd()
    file_paths = get_files_list(cwd)

    for file in file_paths:
        # Todo: upload file to the data lake

        # After uploading, move the file to the 'sent' folder
        move_to_sent_folder(file, cwd)



if __name__ == "__main__":
    main()
