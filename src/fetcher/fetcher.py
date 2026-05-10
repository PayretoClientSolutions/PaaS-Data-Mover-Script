import logging
import os
import time
from pathlib import Path

import paramiko
from google.cloud import storage

from models import BIPSummary, FileResult, SFTPConfig
from sender import Sender


class Fetcher:
    def __init__(
        self, config: SFTPConfig, email_sender: Sender, bip_name: str = "UNKNOWN"
    ) -> None:
        self.hostname = config.hostname
        self.email_sender = email_sender
        self.bip_name = bip_name
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.path_to_key = os.path.expanduser(config.path_to_key)
        self.local_path = os.path.expanduser(config.local_path)
        self.target_file_type = config.target_file_type
        self.remote_path = config.remote_path
        self.bucket_name = config.bucket_name
        self.path_to_gcs_credentials = config.path_to_gcs_credentials

        # init google GCS credentials
        logging.info("Initializing Google Cloud Storage client.")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.path_to_gcs_credentials
        try:
            self.gcs_client = storage.Client()
        except Exception as e:
            error_msg = f"Failed to initialize Google Cloud Storage client: {e}"
            logging.error(error_msg)
            self._safe_notify(subject=" - Error Notification", body=error_msg)
            raise RuntimeError(error_msg)

        logging.info(f"Checking if local_path exists: {self.local_path}")
        if not os.path.exists(self.local_path):
            error_msg = f"Required directory '{self.local_path}' does not exist."
            logging.fatal(error_msg)
            self._safe_notify(subject=" - Error Notification", body=error_msg)
            raise RuntimeError(error_msg)

        logging.info(
            "Fetcher initialized with the following parameters: "
            f"hostname={self.hostname}, port={self.port}, username={self.username}, "
            f"local_path={self.local_path}, path_to_key={self.path_to_key}, "
            f"target_file_type={self.target_file_type}, remote_path={self.remote_path}"
        )

    def _safe_notify(self, *, subject: str, body: str) -> None:
        """
        Sends notification email without interrupting error handling
        when SMTP delivery itself fails.
        """
        try:
            self.email_sender.send(subject=subject, body=body)
        except Exception as notify_error:
            logging.error(f"Failed to send notification email: {notify_error}")

    def _upload_file_to_gcs(self, file_path: Path, bucket) -> bool:
        """
        Uploads a file to Google Cloud Storage.
        Returns True if upload is successful, False otherwise.
        This function assumes that the GCS bucket already exists.
        The GCS credentials file renamed to 'gcs.json' must be located in the current working directory.
        """

        # Upload the file.
        try:
            logging.info(f"Uploading file {file_path.name}")
            blob = bucket.blob(file_path.name)
            blob.upload_from_filename(filename=str(file_path))
            return True

        except Exception as e:
            error_msg = f"Failed to upload file {file_path.name}: {e}"
            logging.error(error_msg)
            self._safe_notify(subject=" - Error Notification", body=error_msg)
            return False

    def fetch_files(self) -> BIPSummary:
        """
        Connects to the remote server and fetches files from the specified remote path to the local path.
        Returns a BIPSummary capturing the results of the run.
        """
        # Result tracking lists
        downloaded: list[FileResult] = []
        deleted: list[FileResult] = []
        failed_downloads: list[FileResult] = []
        failed_deletions: list[FileResult] = []
        target_files: list[str] = []

        # Initialize SSH client
        SSH_Client = paramiko.SSHClient()
        SSH_Client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Record total runtime start
        overall_start = time.perf_counter()

        # attempt connection
        try:
            logging.info(
                f"Attempting to connect to {self.hostname}:{self.port} as {self.username}"
            )

            # Require key-based auth only
            if not self.path_to_key:
                error_msg = "SFTP key path not provided; this script requires key-based authentication."
                logging.fatal(error_msg)
                self._safe_notify(subject=" - Error Notification", body=error_msg)
                duration = time.perf_counter() - overall_start
                return BIPSummary(
                    bip_name=self.bip_name,
                    files_found=0,
                    downloaded=[],
                    deleted=[],
                    failed_downloads=[],
                    failed_deletions=[],
                    duration_s=duration,
                    status="failed",
                )

            # Load the private key (supports RSA, DSA, ECDSA, Ed25519, and OpenSSH format)
            private_key = None
            key_load_error = None

            # ACI's SFTP server only supports Ed25519 and 4096-bit RSA keys
            key_attempt_errors: list[str] = []
            for key_class in (paramiko.RSAKey, paramiko.Ed25519Key):
                try:
                    private_key = key_class.from_private_key_file(
                        self.path_to_key, password=self.password
                    )

                    # If RSA, enforce 4096-bit length
                    if isinstance(private_key, paramiko.RSAKey):
                        bits = None
                        if hasattr(private_key, "get_bits"):
                            bits = private_key.get_bits()
                        elif hasattr(private_key, "bits"):
                            bits = getattr(private_key, "bits")
                        if bits != 4096:
                            logging.fatal(
                                f"RSA key loaded but key size is {bits}; server requires 4096-bit RSA."
                            )
                            duration = time.perf_counter() - overall_start
                            return BIPSummary(
                                bip_name=self.bip_name,
                                files_found=0,
                                downloaded=[],
                                deleted=[],
                                failed_downloads=[],
                                failed_deletions=[],
                                duration_s=duration,
                                status="failed",
                            )

                    logging.info(f"Successfully loaded {key_class.__name__}")
                    break
                except paramiko.SSHException as e:
                    msg = f"{key_class.__name__} failed: {e}"
                    logging.warning(msg)
                    key_attempt_errors.append(msg)
                    continue
                except Exception as e:
                    key_load_error = e
                    key_attempt_errors.append(f"{key_class.__name__} failed: {e}")
                    continue

            if private_key is None:
                error_msg = f"Failed to load private key from {self.path_to_key}"
                if key_attempt_errors:
                    error_msg += "; " + "; ".join(key_attempt_errors)
                elif key_load_error:
                    error_msg += f": {key_load_error}"
                logging.fatal(error_msg)
                self._safe_notify(subject=" - Error Notification", body=error_msg)
                duration = time.perf_counter() - overall_start
                return BIPSummary(
                    bip_name=self.bip_name,
                    files_found=0,
                    downloaded=[],
                    deleted=[],
                    failed_downloads=[],
                    failed_deletions=[],
                    duration_s=duration,
                    status="failed",
                )

            SSH_Client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                pkey=private_key,
                look_for_keys=False,
                allow_agent=False,
                timeout=30,
            )
        except Exception as e:
            error_msg = f"Failed to connect to {self.hostname}: {e}"
            logging.fatal(error_msg)
            self._safe_notify(subject=" - Error Notification", body=error_msg)
            duration = time.perf_counter() - overall_start
            return BIPSummary(
                bip_name=self.bip_name,
                files_found=0,
                downloaded=[],
                deleted=[],
                failed_downloads=[],
                failed_deletions=[],
                duration_s=duration,
                status="failed",
            )

        # open SFTP session
        try:
            logging.info(f"Connecting to {self.hostname} via SFTP...")
            sftp_client = SSH_Client.open_sftp()

            # list target files in the remote directory
            remote_files = sftp_client.listdir(self.remote_path)
            target_files = [
                f for f in remote_files if f.endswith(self.target_file_type)
            ]

            if not target_files:
                logging.info(
                    f"No {self.target_file_type} file(s) found in path '{self.remote_path}'.  Exiting..."
                )
                self._safe_notify(
                    subject=" - No Files Found",
                    body=(
                        f"[BIP: {self.bip_name}] No {self.target_file_type} file(s) found "
                        f"in remote path '{self.remote_path}' on host {self.hostname}."
                    ),
                )
                duration = time.perf_counter() - overall_start
                return BIPSummary(
                    bip_name=self.bip_name,
                    files_found=0,
                    downloaded=[],
                    deleted=[],
                    failed_downloads=[],
                    failed_deletions=[],
                    duration_s=duration,
                    status="no_files",
                )

            logging.info(
                f"Found: {len(target_files)} {self.target_file_type} file(s) in path '{self.remote_path}'"
            )

            # fetch GCS bucket once before the loop
            try:
                bucket = self.gcs_client.get_bucket(self.bucket_name)
            except Exception as e:
                error_msg = f"Could not access GCS bucket '{self.bucket_name}': {e}"
                logging.fatal(error_msg)
                self._safe_notify(subject=" - Error Notification", body=error_msg)
                duration = time.perf_counter() - overall_start
                return BIPSummary(
                    bip_name=self.bip_name,
                    files_found=len(target_files),
                    downloaded=[],
                    deleted=[],
                    failed_downloads=[],
                    failed_deletions=[],
                    duration_s=duration,
                    status="failed",
                )

            for file_name in target_files:
                remote_file_path = f"{self.remote_path}/{file_name}"
                local_file_path = f"{self.local_path}/{file_name}"

                # download the file
                try:
                    logging.info(f"Downloading file {file_name}")
                    sftp_client.get(remote_file_path, local_file_path)
                    downloaded.append(
                        FileResult(name=file_name, success=True, stage="download")
                    )
                    logging.info(
                        f"{len(downloaded)}/{len(target_files)} downloaded so far."
                    )

                    # upload to GCS and delete local copy if upload is successful
                    upload_success = False
                    local_file: Path = Path(local_file_path)
                    upload_success = self._upload_file_to_gcs(local_file, bucket)
                    if upload_success:
                        logging.info("Upload SUCCESSFUL! Deleting local copy.")
                        local_file.unlink()
                    else:
                        logging.error("Upload FAILED! retaining local copy.")
                        # Remove from downloaded since upload failed
                        downloaded = [d for d in downloaded if d.name != file_name]
                        failed_downloads.append(
                            FileResult(
                                name=file_name,
                                success=False,
                                stage="upload",
                                error_message="Upload to GCS failed",
                            )
                        )
                except KeyboardInterrupt:
                    logging.warning("Download interrupted by user. Exiting...")
                    duration = time.perf_counter() - overall_start
                    return BIPSummary(
                        bip_name=self.bip_name,
                        files_found=len(target_files),
                        downloaded=downloaded,
                        deleted=deleted,
                        failed_downloads=failed_downloads,
                        failed_deletions=failed_deletions,
                        duration_s=duration,
                        status="failed",
                    )
                except Exception as e:
                    error_msg = (
                        f"[BIP: {self.bip_name}] Failed to download file '{file_name}' "
                        f"from '{remote_file_path}' to '{local_file_path}': {e}"
                    )
                    logging.error(error_msg)
                    self._safe_notify(subject=" - Error Notification", body=error_msg)
                    failed_downloads.append(
                        FileResult(
                            name=file_name,
                            success=False,
                            stage="download",
                            error_message=str(e),
                        )
                    )
                    continue  # skip deletion if download failed

                # Delete the remote file only if upload succeeded
                if upload_success:
                    try:
                        logging.info(f"Deleting remote file {file_name}")
                        sftp_client.remove(remote_file_path)
                        deleted.append(
                            FileResult(name=file_name, success=True, stage="delete")
                        )
                    except KeyboardInterrupt:
                        logging.warning("Delete interrupted by user. Exiting...")
                        duration = time.perf_counter() - overall_start
                        return BIPSummary(
                            bip_name=self.bip_name,
                            files_found=len(target_files),
                            downloaded=downloaded,
                            deleted=deleted,
                            failed_downloads=failed_downloads,
                            failed_deletions=failed_deletions,
                            duration_s=duration,
                            status="partial"
                            if (failed_downloads or failed_deletions)
                            else "success",
                        )
                    except Exception as e:
                        logging.error(f"Failed to remove {file_name}: {e}")
                        failed_deletions.append(
                            FileResult(
                                name=file_name,
                                success=False,
                                stage="delete",
                                error_message=str(e),
                            )
                        )
                else:
                    logging.warning(
                        f"Skipping remote deletion for {file_name} because upload failed."
                    )

                time.sleep(1)

            duration = time.perf_counter() - overall_start

            # Determine status
            if failed_downloads or failed_deletions:
                status = "partial"
                logging.warning("Some operations failed - review logs above")
            else:
                status = "success"

            # summary logging
            logging.info(
                f"Process complete: {len(downloaded)} downloaded, "
                f"{len(failed_downloads)} FAILED downloads, "
                f"{len(failed_deletions)} FAILED deletions, "
                f"timed for {duration:.6f} seconds."
            )

            return BIPSummary(
                bip_name=self.bip_name,
                files_found=len(target_files),
                downloaded=downloaded,
                deleted=deleted,
                failed_downloads=failed_downloads,
                failed_deletions=failed_deletions,
                duration_s=duration,
                status=status,
            )

        except Exception as e:
            logging.fatal(f"Failed to open SFTP session: {e}")
            duration = time.perf_counter() - overall_start
            return BIPSummary(
                bip_name=self.bip_name,
                files_found=len(target_files),
                downloaded=downloaded,
                deleted=deleted,
                failed_downloads=failed_downloads,
                failed_deletions=failed_deletions,
                duration_s=duration,
                status="failed",
            )

        finally:
            # ensure SSH connection is always closed
            if SSH_Client:
                logging.info("Finally closing session.")
                SSH_Client.close()
