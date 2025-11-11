import logging
import os
import sys
import time

import paramiko


class Fetcher:
    def __init__(
            self,
            hostname: str,
            port: int,
            username: str,
            password: str,
            path_to_key: str,
            local_path: str,
            target_file_type: str = '.csv',
            remote_path: str = "./pub/example") -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.path_to_key = os.path.expanduser(path_to_key)
        self.local_path = os.path.expanduser(local_path)
        self.target_file_type = target_file_type
        self.remote_path = remote_path

        logging.info(
            "Fetcher initialized with the following parameters: "
            f"hostname={hostname}, port={port}, username={username}, "
            f"local_path={local_path}, path_to_key={path_to_key}, "
            f"target_file_type={target_file_type}, remote_path={remote_path}"
        )

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

            # Require key-based auth only
            if not self.path_to_key:
                logging.fatal(
                    "SFTP key path not provided; this script requires key-based authentication.")
                sys.exit(1)

            # Load the private key (supports RSA, DSA, ECDSA, Ed25519, and OpenSSH format)
            private_key = None
            key_load_error = None

            # ACI's SFTP server only supports Ed25519 and 4096-bit RSA keys
            for key_class in (paramiko.Ed25519Key, paramiko.RSAKey):
                try:
                    private_key = key_class.from_private_key_file(
                        self.path_to_key,
                        password=self.password
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
                                f"RSA key loaded but key size is {bits}; server requires 4096-bit RSA.")
                            return

                    logging.info(f"Successfully loaded {key_class.__name__}")
                    break
                except paramiko.SSHException:
                    continue
                except Exception as e:
                    key_load_error = e
                    continue

            if private_key is None:
                error_msg = f"Failed to load private key from {self.path_to_key}"
                if key_load_error:
                    error_msg += f": {key_load_error}"
                logging.fatal(error_msg)
                sys.exit(1)

            SSH_Client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                pkey=private_key,
                look_for_keys=False,
                allow_agent=False
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
            return
        finally:
            # ensure SSH connection is always closed
            if SSH_Client:
                SSH_Client.close()
