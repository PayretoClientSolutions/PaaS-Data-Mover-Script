import logging
import sys
import time

import paramiko


class Fetcher:
    def __init__(self, hostname: str, port: int, username: str, password: str, local_path: str, target_file_type: str = '.csv', remote_path: str = "/pub/example") -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.local_path = local_path
        self.target_file_type = target_file_type
        self.remote_path = remote_path

    def fetch_files(self) -> None:
        """
        Connects to the remote server and fetches files from the specified remote path to the local path.
        """

        # initialize SSH client
        SSH_Client = paramiko.SSHClient()
        SSH_Client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # attempt connection
        try:
            logging.info(
                f"Attempting to connect to {self.hostname}:{self.port} as {self.username}")

            SSH_Client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                look_for_keys=False
            )
        except Exception as e:
            logging.fatal(f"Failed to connect to {self.hostname}: {e}")
            sys.exit(1)

        # open SFTP session
        try:
            start_time = time.perf_counter()
            logging.info(f"Connecting to {self.hostname} via SFTP...")
            sftp_client = SSH_Client.open_sftp()

            # list target files in the remote directory
            remote_files = sftp_client.listdir(self.remote_path)
            target_files = [f for f in remote_files if f.endswith(
                self.target_file_type)
            ]

            # exit if no files found
            if not target_files:
                logging.info(
                    f"No {self.target_file_type} file(s) found in path '{self.remote_path}'.  Exiting...")
                return

            logging.info(
                f"Found: {len(target_files)} {self.target_file_type} file(s) in path '{self.remote_path}'")

            # tracking
            downloaded_files = []
            failed_downloads = []
            failed_deletions = []

            for file_name in target_files:
                remote_file_path = f"{self.remote_path}/{file_name}"
                local_file_path = f"{self.local_path}/{file_name}"

                # download the file
                try:
                    logging.info(f"Downloading file {file_name}")
                    sftp_client.get(remote_file_path, local_file_path)
                    downloaded_files.append(file_name)
                except Exception as e:
                    logging.error(f"Failed to download {file_name}: {e}")
                    failed_downloads.append(file_name)
                    continue  # skip deletion if download failed

                # Delete the file from server if the download succeeded
                try:
                    logging.info(f"Deleting remote file {file_name}")
                    sftp_client.remove(remote_file_path)
                except Exception as e:
                    logging.error(f"Failed to remove {file_name}: {e}")
                    failed_deletions.append(file_name)

            end = time.perf_counter()

            # summary logging
            logging.info(
                f"Process complete: {len(downloaded_files)} downloaded, "
                f"{len(failed_downloads)} FAILED downloads, "
                f"{len(failed_deletions)} FAILED deletions, "
                f"timed for {end - start_time:.6f} seconds."
            )

            if failed_downloads or failed_deletions:
                logging.warning(f"Some operations failed - review logs above")

            logging.info("Closing session.")
            SSH_Client.close()
        except Exception as e:
            logging.fatal(f"Failed to open SFTP session: {e}")
            sys.exit(1)
        finally:
            # ensure SSH connection is always closed
            if SSH_Client:
                SSH_Client.close()
