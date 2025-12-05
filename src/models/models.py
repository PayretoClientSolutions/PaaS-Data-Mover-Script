from dataclasses import dataclass
from pathlib import Path


@dataclass
class SFTPConfig:
    """
    configuration for SFTP connections per BIP.

    Attributes:
        hostname (str): The hostname of the SFTP server.
        username (str): The username for SFTP authentication.
        port (int): The port number for the SFTP connection.
        password (str): The password for SFTP authentication.
        path_to_key (str): The path to the private key file for key-based authentication.
        local_path (str): The local directory path for file downloads.
        target_file_type (str): The target file type for processing, default is ".csv".
        remote_path (str): The remote directory path on the SFTP server, default is "/REPORTS".
    """
    hostname: str
    username: str
    port: int
    password: str
    path_to_key: str
    local_path: str
    target_file_type: str = ".csv"
    remote_path: str = "/REPORTS"


@dataclass
class MoverConfig:
    """
    Mover configuration.

    Attributes:
        working_dir (Path): Directory where files were initially downloaded.
        sent_dir (Path): Directory where processed files are moved after handling.
        path_to_gcs_credentials (str): Path to Google Cloud Storage credentials file.
    """
    working_dir: Path
    sent_dir: Path
    path_to_gcs_credentials: str
