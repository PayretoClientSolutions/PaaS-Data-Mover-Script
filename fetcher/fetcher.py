import logging
import sys

import paramiko


class Fetcher:
    def __init__(self, hostname: str, port: int, username: str, password: str,  local_path: str) -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.remote_path = "."
        self.local_path = local_path

    def fetch_files(self) -> None:
        """
        Connects to the remote server and fetches files from the specified remote path to the local path.
        """

        # initialize SSH client
        SSH_Client = paramiko.SSHClient()
        SSH_Client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

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

        try:
            logging.info(f"Connecting to {self.hostname} via SFTP.")
            sftp_client = SSH_Client.open_sftp()

            logging.info("Closing session.")
            SSH_Client.close()

        except Exception as e:
            logging.fatal(f"Failed to open SFTP session: {e}")
            sys.exit(1)
