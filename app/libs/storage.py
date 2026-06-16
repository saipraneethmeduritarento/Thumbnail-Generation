import os
from dotenv import load_dotenv

from ..logger import logger
from .base_storage import Storage
from google.cloud import storage
from google.oauth2 import service_account

load_dotenv()

class GCPStorage(Storage):
    __client__ = None

    def __init__(self):
        logger.info("Initializing GCP Storage") 
        bucket_name = os.getenv("GCP_BUCKET_NAME")
        storage_credentials_json = os.getenv("GCP_STORAGE_CREDENTIALS")

        if not bucket_name or not storage_credentials_json:
            raise ValueError(
                "GCPStorage client not initialized. Missing google bucket_name or crendentials")
        
        credentials = service_account.Credentials.from_service_account_file(storage_credentials_json)
        self.__bucket_name__ = bucket_name
        self.__client__ = storage.Client(credentials=credentials)
        # os.makedirs(self.tmp_folder, exist_ok=True)


    def write_file(
        self,
        file_path: str,
        file_content: str | bytes,
        mime_type: str | None = None,
    ):
        if not self.__client__:
            raise ValueError("GCPSStorage client not initialized")

        bucket = self.__client__.bucket(self.__bucket_name__)
        blob = bucket.blob(file_path)

        if mime_type is None:
            mime_type = (
                "image/jpeg"
                if file_path.lower().endswith(".jpg") or file_path.lower().endswith(".jpeg")
                else "image/png"
            )
        blob.upload_from_string(file_content, content_type=mime_type)
        logger.info(f"File uploaded to GCP bucket: {file_path}")

    def public_url(self, file_path: str) -> str:
        if not self.__client__:
            raise ValueError("GCP Storage client not initialized")

        bucket = self.__client__.bucket(self.__bucket_name__)
        blob = bucket.blob(file_path)
        blob.make_public()
        logger.debug(f"GCP Public URL :: {blob.public_url}")
        return blob.public_url