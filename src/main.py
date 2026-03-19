import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient

from fetcher import Fetcher
from models import SFTPConfig
from models.models import EmailConfig, InfisicalConfig
from sender import Sender

# from mover import Mover


def init_logger() -> None:
    """
    Initializes the logger for the whole script
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log", mode="a"),  # Logs to a file.
            logging.StreamHandler(),  # Logs to console.
        ],
    )


def init_sender() -> Sender:
    """
    Initializes the Sender class for email notifications.
    Returns:
        Sender: An instance of the Sender class configured with SMTP settings.
    """
    email_cfg = EmailConfig(
        host=os.environ.get("SMTP_HOST", ""),
        port=int(os.environ.get("SMTP_PORT", "587")),
        username=os.environ.get("SMTP_USERNAME"),
        password=os.environ.get("SMTP_PASSWORD"),
        from_addr=os.environ.get("SMTP_FROM_ADDR", ""),
        to_addrs=os.environ.get("SMTP_TO_ADDRS", "").split(","),
        use_tls=os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
        use_ssl=os.environ.get("SMTP_USE_SSL", "false").lower() == "true",
        subject_prefix=os.environ.get(
            "SMTP_SUBJECT_PREFIX", "[PaaS-Data-Mover]"),
        app_name=os.environ.get("APP_NAME", "PaaS-Data-Mover"),
    )

    return Sender(config=email_cfg)


def init_infisical_client() -> InfisicalConfig:
    """
    Initializes the Infisical SDK client for fetching secrets.
    Returns:
        InfisicalConfig: An instance of the InfisicalConfig configured with the necessary parameters.
    """

    # read environment variables from .env file
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
    if not env_path.exists():
        logging.error(f"Environment file not found at: {env_path}")
        sys.exit(1)

    load_dotenv(env_path)

    try:
        logging.info("Fetching secrets from Infisical...")
        client = InfisicalSDKClient(
            host="https://eu.infisical.com", token=os.environ.get("INFISICAL_TOKEN", "")
        )

        project_id = os.environ.get("INFISICAL_PROJECT_ID", "")
        project_slug = os.environ.get("INFIISCAL_PROJECT_SLUG", "")
        environment_slug = os.environ.get("INFISICAL_ENVIRONMENT", "dev")

        return InfisicalConfig(
            client=client,
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
        )
    except Exception as e:
        logging.error(f"Error initializing Infisical client: {e}")
        raise


def fetch_and_move(
    bip_name: str,
    sc_dct: dict[str, str],
    path_to_gcs_file: Path,
) -> None:
    """
    Fetches files via SFTP and moves them to GCS.
    Parameters:
        bip_name (str): Name of the BIP
        sc_dct (dict[str, str]): Secrets dictionary
        path_to_gcs_file (Path): Path to GCS credentials file
    """

    # map to SFTPConfig dataclass
    sftp_conf = SFTPConfig(
        hostname=sc_dct.get("HOSTNAME", ""),
        username=sc_dct.get("USERNAME", ""),
        port=int(sc_dct.get("PORT", "22")),
        password=sc_dct.get("PASSWORD", ""),
        path_to_key=sc_dct.get("PATH_TO_KEY", ""),
        local_path=sc_dct.get("LOCAL_PATH", "."),
        bucket_name=sc_dct.get("BUCKET_NAME", ""),
        path_to_gcs_credentials=str(path_to_gcs_file),
    )

    # initialize Fetcher class
    logging.info(
        f"> > > > > FETCHER task started for {bip_name} < < < < <")

    try:
        Fetcher(config=sftp_conf).fetch_files()

    except SystemExit as e:
        logging.error(
            f"SystemExit occurred while running Fetcher for {bip_name}: {e}")
        return

    except Exception as e:
        logging.error(
            f"Error occurred while running Fetcher for {bip_name}: {e}")
        return


def main() -> None:
    # Start logging both in the terminal and the log file.
    init_logger()
    logging.info("Script started.")

    # init infisical client for fetching secrets
    infisical_config = init_infisical_client()
    client = infisical_config.client
    project_id = infisical_config.project_id
    project_slug = infisical_config.project_slug
    environment_slug = infisical_config.environment_slug

    # init email sender for notifications
    # email_sender = init_sender()
    # email_sender.send_email()

    # init path to gcs credentials file
    path_to_gcs_file = Path(__file__).parents[1] / "config" / "gcs.json"

    # fetch all secrets per BIP
    try:
        # fetch secrets for PRTPE_TEST
        sc_prtpe_test = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/prtpe_test",
        ).secrets
        sc_dct_prtpe_test = {
            sc.secretKey: sc.secretValue for sc in sc_prtpe_test}

        # fetch secrets for PRTSO_TEST
        sc_prtso_test = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/prtso_test",
        ).secrets
        sc_dct_prtso_test = {
            sc.secretKey: sc.secretValue for sc in sc_prtso_test}

        # fetch secrets for SOLID_TEST
        sc_solid_test = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/solid_test",
        ).secrets
        sc_dct_solid_test = {
            sc.secretKey: sc.secretValue for sc in sc_solid_test}

        # fetch secrets for BIGE_TEST
        sc_bige_test = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/bige_test",
        ).secrets
        sc_dct_bige_test = {
            sc.secretKey: sc.secretValue for sc in sc_bige_test}

        # fetch secrets for PRTPE
        sc_prtpe = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/prtpe",
        ).secrets
        sc_dct_prtpe = {sc.secretKey: sc.secretValue for sc in sc_prtpe}

        # fetch secrets for PRTSO
        sc_prtso = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/prtso",
        ).secrets
        sc_dct_prtso = {sc.secretKey: sc.secretValue for sc in sc_prtso}

        # fetch secrets for SOLID
        sc_solid = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/solid",
        ).secrets
        sc_dct_solid = {sc.secretKey: sc.secretValue for sc in sc_solid}

        # fetch secrets for BIGE
        sc_bige = client.secrets.list_secrets(
            project_id=project_id,
            project_slug=project_slug,
            environment_slug=environment_slug,
            secret_path="/bige",
        ).secrets
        sc_dct_bige = {sc.secretKey: sc.secretValue for sc in sc_bige}

    except Exception as e:
        logging.error(f"Error fetching secrets from Infisical: {e}")
        return

    # PRTPE_TEST
    fetch_and_move(
        bip_name="PRTPE_TEST",
        sc_dct=sc_dct_prtpe_test,
        path_to_gcs_file=path_to_gcs_file,
    )

    # # PRTSO_TEST
    # fetch_and_move(
    #     bip_name="PRTSO_TEST",
    #     sc_dct=sc_dct_prtso_test,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # SOLID_TEST
    # fetch_and_move(
    #     bip_name="SOLID_TEST",
    #     sc_dct=sc_dct_solid_test,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # BIGE_TEST
    # fetch_and_move(
    #     bip_name="BIGE_TEST",
    #     sc_dct=sc_dct_bige_test,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # PRTPE
    # fetch_and_move(
    #     bip_name="PRTPE",
    #     sc_dct=sc_dct_prtpe,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # PRTSO
    # fetch_and_move(
    #     bip_name="PRTSO",
    #     sc_dct=sc_dct_prtso,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # SOLID
    # fetch_and_move(
    #     bip_name="SOLID",
    #     sc_dct=sc_dct_solid,
    #     path_to_gcs_file=path_to_gcs_file,
    # )

    # # BIGE
    # fetch_and_move(
    #     bip_name="BIGE",
    #     sc_dct=sc_dct_bige,
    #     path_to_gcs_file=path_to_gcs_file,
    # )


if __name__ == "__main__":
    main()
