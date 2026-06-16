from abc import ABC, abstractmethod

class Storage(ABC):
    @abstractmethod
    def write_file(
        self,
        file_path: str,
        file_content: str | bytes,
        mime_type: str | None = None,
    ):
        """
        Write file to internal storage
        """

    @abstractmethod
    def public_url(self, file_path: str) -> str:
        """
        Make Public URL
        """