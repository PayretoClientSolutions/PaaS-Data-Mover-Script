from dataclasses import dataclass, field
from typing import List

from infisical_sdk import InfisicalSDKClient


@dataclass
class FileResult:
    """Single file outcome inside one BIP."""

    name: str
    success: bool
    stage: str  # e.g. "download", "upload", "delete"
    error_message: str = ""


@dataclass
class BIPSummary:
    """Aggregated results for one BIP run."""

    bip_name: str
    files_found: int
    downloaded: list[FileResult]
    deleted: list[FileResult]
    failed_downloads: list[FileResult]
    failed_deletions: list[FileResult]
    duration_s: float
    status: str  # "success", "partial", "failed", or "no_files"

    @property
    def files_succeeded(self) -> int:
        return len(self.downloaded) + len(self.deleted)

    @property
    def files_failed(self) -> int:
        return len(self.failed_downloads) + len(self.failed_deletions)


@dataclass
class SFTPConfig:
    """
    Connection and storage settings for one BIP transfer.

    Attributes:
        hostname: SFTP server hostname.
        username: Username for key-based SFTP authentication.
        port: SFTP server port.
        key_passphrase: Passphrase for the private key file.
        path_to_key: Local path to the private key file.
        local_path: Existing local directory used for downloads before upload.
        bucket_name: Destination GCS bucket.
        path_to_gcs_credentials: Local path to the GCS service account key.
        target_file_type: Remote file suffix to process.
        remote_path: Remote SFTP directory to scan.
    """
    hostname: str
    username: str
    port: int
    key_passphrase: str
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
        host: SMTP server hostname.
        port: SMTP server port, such as 587 for STARTTLS or 465 for SSL.
        username: SMTP username, if authentication is required.
        password: SMTP password, if authentication is required.
        from_addr: Sender email address used in the From header.
        to_addrs: Default recipient email addresses.
        use_tls: Upgrade the connection with STARTTLS after connecting.
        use_ssl: Use implicit SSL from connection start. If true, STARTTLS is ignored.
        subject_prefix: Optional prefix for all outbound message subjects.
        app_name: Application name used in generated exception subjects.
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


@dataclass
class InfisicalConfig:
    """
    Configuration for Infisical SDK client.

    Attributes:
        client: InfisicalSDKClient configured with the host and token.
        project_id: Infisical project ID.
        project_slug: Infisical project slug.
        environment_slug: Infisical environment slug, such as "dev".
    """

    client: InfisicalSDKClient
    project_id: str
    project_slug: str
    environment_slug: str
