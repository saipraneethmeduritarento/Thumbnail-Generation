"""
Shared test fixtures for the Thumbnail Generation API.

All required environment variables and GCP/Vertex AI patches are applied
at module load time — BEFORE any app import — because app/services/image_variation.py
and app/libs/storage.py execute side-effectful code at module level:

  - app/services/image_variation.py:20  — reads KB_API_HOST from env
  - app/services/image_variation.py:22  — reads STORAGE_THUMBNAIL_FOLDER
  - app/services/image_variation.py:23  — reads STORAGE_PROXY_PATH
  - app/services/image_variation.py:27  — reads GCP_GEMINI_CREDENTIALS
  - app/services/image_variation.py:28-29 — calls vertexai.init(...)
  - app/services/image_variation.py:31-33 — reads GEMINI_MODEL_PRO, VISION_MODEL, NUMBER_OF_IMAGES
  - app/libs/storage.py:31-34            — reads GCP_BUCKET_NAME, GCP_STORAGE_CREDENTIALS,
                                           calls service_account.Credentials.from_service_account_file
  - app/logger.py:14                     — reads LOG_LEVEL
"""

import os
from unittest.mock import MagicMock, patch

# ── Required env vars — must be set BEFORE any app import ─────────────────
os.environ.setdefault("KB_API_HOST", "http://test-kb-host.example.test")
os.environ.setdefault("STORAGE_THUMBNAIL_FOLDER", "test/thumbnails")
os.environ.setdefault("STORAGE_PROXY_PATH", "test/proxy")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_STORAGE_CREDENTIALS", "/tmp/test-gcp-creds.json")
os.environ.setdefault("GCP_GEMINI_CREDENTIALS", "/tmp/test-gemini-creds.json")
os.environ.setdefault("GCP_GEMINI_PROJECT_ID", "test-project-00000000")
os.environ.setdefault("GEMINI_MODEL_PRO", "gemini-1.5-pro-001")
os.environ.setdefault("VISION_MODEL", "imagegeneration@006")
os.environ.setdefault("NUMBER_OF_IMAGES", "4")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest  # noqa: E402

# ── Patch GCP/Vertex module-level initialization before app import ────────
#
# GCPStorage.__init__ calls:
#   service_account.Credentials.from_service_account_file(path) [app/libs/storage.py:33]
#   storage.Client(credentials=...) [app/libs/storage.py:34]
#
# image_variation.py module-level calls:
#   vertexai.init(project=...) [app/services/image_variation.py:28-29]
#
# Patches are started before the import and stopped immediately after.
# The GCPStorage instance (app.services.image_variation.storage) will have
# __client__ = MagicMock() for the duration of the test session.
_patch_creds = patch(
    "google.oauth2.service_account.Credentials.from_service_account_file",
    return_value=MagicMock(),
)
_patch_storage_client = patch(
    "google.cloud.storage.Client",
    return_value=MagicMock(),
)
_patch_vertexai_init = patch("vertexai.init", return_value=None)

_patch_creds.start()
_patch_storage_client.start()
_patch_vertexai_init.start()

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402  [app/main.py:9]

_patch_creds.stop()
_patch_storage_client.stop()
_patch_vertexai_init.stop()


@pytest.fixture
def client():
    """Synchronous ASGI test client.

    Routes in this project are synchronous (not async):
      - generate_course_image_variations [app/routers/course.py:31]
      - generate_image                   [app/routers/resource.py:9]
    starlette.testclient.TestClient is the correct choice here.
    """
    with TestClient(app) as c:
        yield c
