from dataclasses import dataclass
from pathlib import Path


@dataclass
class SFTPConfig:
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
    working_dir: Path
    sent_dir: Path
    path_to_gcs_credentials: str
