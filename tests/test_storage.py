"""
Unit tests for app/libs/storage.py  →  GCPStorage

Methods tested:
  GCPStorage.write_file(file_path, file_content, mime_type)  [app/libs/storage.py:44-64]
  GCPStorage.public_url(file_path)                           [app/libs/storage.py:66-74]

GCPStorage.__init__ calls service_account.Credentials.from_service_account_file and
storage.Client — both are patched at module load in conftest.py so the instance is
safe to create. Per-test patches replace __client__ with a MagicMock.

S8405: no HTTP client calls via TestClient in this file.
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# Import the class under test — safe: conftest.py already patched GCP init
from app.libs.storage import GCPStorage


def _make_storage_instance():
    """Create a GCPStorage instance with a mock GCP client.

    conftest.py patches service_account.Credentials.from_service_account_file and
    storage.Client only during the initial app import, then stops the patches.
    Storage unit tests must re-apply the patches while calling GCPStorage() directly.
    After construction, replace __client__ with a plain MagicMock to control behavior.
    """
    with (
        patch("google.oauth2.service_account.Credentials.from_service_account_file",
              return_value=MagicMock()),
        patch("google.cloud.storage.Client", return_value=MagicMock()),
    ):
        instance = GCPStorage()
    instance.__client__ = MagicMock()
    instance.__bucket_name__ = "test-bucket"
    return instance


# ── write_file ─────────────────────────────────────────────────────────────


def test_write_file_uploads_bytes_to_gcs():
    """Happy path: bytes content uploaded via blob.upload_from_string.

    [app/libs/storage.py:55-57, 61-62]
    """
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    gcs.write_file("thumbnails/test/img.jpg", b"fake-bytes", "image/jpeg")

    gcs.__client__.bucket.assert_called_once_with("test-bucket")
    mock_blob.upload_from_string.assert_called_once_with(b"fake-bytes", content_type="image/jpeg")


def test_write_file_infers_jpeg_mime_type_from_jpg_extension():
    """mime_type=None + .jpg extension → 'image/jpeg' inferred [app/libs/storage.py:54-58]."""
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    gcs.write_file("thumbnails/img.jpg", b"bytes", mime_type=None)

    call_kwargs = mock_blob.upload_from_string.call_args
    assert call_kwargs[1]["content_type"] == "image/jpeg"


def test_write_file_infers_jpeg_mime_type_from_jpeg_extension():
    """mime_type=None + .jpeg extension → 'image/jpeg' inferred [app/libs/storage.py:56]."""
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    gcs.write_file("thumbnails/photo.jpeg", b"bytes", mime_type=None)

    call_kwargs = mock_blob.upload_from_string.call_args
    assert call_kwargs[1]["content_type"] == "image/jpeg"


def test_write_file_infers_png_mime_type_from_non_jpg_extension():
    """mime_type=None + .png extension → 'image/png' (else branch) [app/libs/storage.py:58-60]."""
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    gcs.write_file("thumbnails/img.png", b"bytes", mime_type=None)

    call_kwargs = mock_blob.upload_from_string.call_args
    assert call_kwargs[1]["content_type"] == "image/png"


def test_write_file_explicit_mime_type_not_overridden():
    """Explicitly provided mime_type is passed through unchanged [app/libs/storage.py:51]."""
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    gcs.write_file("path/file.unknown", b"bytes", mime_type="application/octet-stream")

    call_kwargs = mock_blob.upload_from_string.call_args
    assert call_kwargs[1]["content_type"] == "application/octet-stream"


def test_write_file_raises_if_client_none():
    """write_file raises Exception if __client__ is None [app/libs/storage.py:52-53]."""
    gcs = _make_storage_instance()
    gcs.__client__ = None

    with pytest.raises(Exception, match="GCPSyncStorage client not initialized"):
        gcs.write_file("path/img.jpg", b"bytes", "image/jpeg")


# ── public_url ─────────────────────────────────────────────────────────────


def test_public_url_returns_blob_public_url():
    """public_url makes blob public and returns blob.public_url [app/libs/storage.py:70-73]."""
    gcs = _make_storage_instance()
    mock_blob = MagicMock()
    mock_blob.public_url = "https://storage.googleapis.com/test-bucket/path/img.jpg"
    gcs.__client__.bucket.return_value.blob.return_value = mock_blob

    result = gcs.public_url("path/img.jpg")

    mock_blob.make_public.assert_called_once()
    assert result == "https://storage.googleapis.com/test-bucket/path/img.jpg"


def test_public_url_raises_if_client_none():
    """public_url raises Exception if __client__ is None [app/libs/storage.py:67-68]."""
    gcs = _make_storage_instance()
    gcs.__client__ = None

    with pytest.raises(Exception, match="GCP Storage client not initialized"):
        gcs.public_url("path/img.jpg")
