import os
from urllib.parse import urlparse

# Constants
ASSET_PREFIX: str = "/assets/public/"
MIME_PNG: str = "image/png"
MIME_JPEG: str = "image/jpeg"
EXT_PNG: str = "png"
EXT_JPEG: str = "jpeg"
EXT_JPG: str = "jpg"

# Default values
DEFAULT_EXTENSION: str = EXT_JPG
DEFAULT_MIME_TYPE: str = MIME_JPEG

# Mappings
MIME_TO_EXTENSION: dict[str, str] = {
    MIME_PNG: EXT_PNG,
    MIME_JPEG: EXT_JPG,
}

EXTENSION_TO_MIME_TYPE: dict[str, str] = {
    EXT_PNG: MIME_PNG,
    EXT_JPEG: MIME_JPEG,
    EXT_JPG: MIME_JPEG,
}

def format_storage_url(image_url: str, asset_prefix = ASSET_PREFIX) -> str:
    urlparts = urlparse(image_url)
    path_parts = urlparts.path.split("/")
    new_url = "https" + "://" + urlparts.netloc + \
        asset_prefix + "/".join(path_parts[2:])
    return new_url

def get_file_extension(file_path: str):
  try:
    parsed_url = urlparse(file_path)
    path = parsed_url.path
    if path:
      _, ext = os.path.splitext(path)
      return ext.lower().lstrip(".") if ext else DEFAULT_EXTENSION
    else:
      return DEFAULT_EXTENSION
  except Exception as e:
    print(f"get_file_extension :: Error parsing URL: {e}")
    return DEFAULT_EXTENSION

def get_file_mimetype(file_path):
  extension = get_file_extension(file_path)
  return EXTENSION_TO_MIME_TYPE.get(extension, DEFAULT_MIME_TYPE)

def get_extension_from_mimetype(mime_type: str) -> str | None:
    # Use a dictionary to map mimetypes to extensions
    return MIME_TO_EXTENSION.get(mime_type.lower(), EXT_PNG)
