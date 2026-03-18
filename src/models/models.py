from dataclasses import dataclass, field
from pathlib import Path
from typing import List


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
    bucket_name: str
    path_to_gcs_credentials: str
    target_file_type: str = ".csv"
    remote_path: str = "/REPORTS"


@dataclass
class EmailConfig:
    """
    Configuration for SMTP email sending.

    Attributes:
        host (str): SMTP server hostname.
        port (int): SMTP server port (e.g., 587 for STARTTLS, 465 for SSL).
        username (str): SMTP username (optional if server allows anonymous or IP-based relaying).
        password (str): SMTP password (optional).
        from_addr (str): The sender email address (From header).
        to_addrs (List[str]): List of recipient email addresses.
        use_tls (bool): Use STARTTLS after connecting (default: True).
        use_ssl (bool): Use implicit SSL (SMTPS) (default: False). If True, STARTTLS is ignored.
        subject_prefix (str): Optional subject prefix for all messages (e.g., "[PaaS-Data-Mover]").
        app_name (str): Optional application name used in default subjects for exception emails.
    """

    host: str
    port: int
    username: str | None = None
    password: str | None = None
    from_addr: str = ""
    to_addrs: List[str] = field(default_factory=list)
    use_tls: bool = True
    use_ssl: bool = False
    subject_prefix: str = ""
    app_name: str = ""


# @dataclass
# class MoverConfig:
#     """
#     Mover configuration.

#     Attributes:
#         working_dir (Path): Directory where files were initially downloaded.
#         sent_dir (Path): Directory where processed files are moved after handling.
#         path_to_gcs_credentials (str): Path to Google Cloud Storage credentials file.
#         bucket_name (str): Name of the Google Cloud Storage bucket to upload files to.
#     """
#     working_dir: Path
#     sent_dir: Path
#     path_to_gcs_credentials: str
#     bucket_name: str  # Default bucket name, can be overridden
