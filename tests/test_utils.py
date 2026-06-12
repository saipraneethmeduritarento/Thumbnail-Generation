"""
Unit tests for app/utils.py

Functions tested:
  format_storage_url(image_url, asset_prefix)  [app/utils.py:10-15]
  get_extension_from_mimetype(mime_type)        [app/utils.py:17-19]

These are pure functions with no external dependencies — no mocks required.
S8405: no HTTP calls in this test file.
"""

from app.utils import format_storage_url, get_extension_from_mimetype, ASSET_PREFIX


# ── format_storage_url ────────────────────────────────────────────────────


def test_format_storage_url_standard_gcs_url():
    """Happy path: GCS-style URL converted to public HTTPS asset URL.

    Input URL structure: <scheme>://<bucket>/<prefix>/<filename>
    Expected: https://<bucket>/assets/public/<filename>
    [app/utils.py:10-15]
    """
    input_url = "https://storage.googleapis.com/bucket-name/thumbnail.jpg"
    result = format_storage_url(input_url)
    assert result.startswith("https://")
    assert "storage.googleapis.com" in result
    assert ASSET_PREFIX.strip("/") in result


def test_format_storage_url_uses_default_asset_prefix():
    """format_storage_url uses ASSET_PREFIX constant as default [app/utils.py:4, 10]."""
    input_url = "https://storage.example.test/bucket/path/to/image.png"
    result = format_storage_url(input_url)
    # Default prefix is /assets/public/ [app/utils.py:4]
    assert "/assets/public/" in result


def test_format_storage_url_custom_asset_prefix():
    """Custom asset_prefix overrides the default [app/utils.py:10]."""
    input_url = "https://storage.example.test/bucket/segment1/segment2/image.jpg"
    result = format_storage_url(input_url, asset_prefix="/custom/prefix/")
    assert "/custom/prefix/" in result


def test_format_storage_url_returns_string():
    """Return type must be str [app/utils.py:10]."""
    result = format_storage_url("https://storage.example.test/b/a/b/c.jpg")
    assert isinstance(result, str)


def test_format_storage_url_https_scheme():
    """Output URL always starts with https:// [app/utils.py:13].

    The function hardcodes 'https' + '://' regardless of the input scheme.
    """
    # HTTP input — output is still https
    result = format_storage_url("http://storage.example.test/bucket/path/img.jpg")
    assert result.startswith("https://")


def test_format_storage_url_preserves_netloc():
    """Network location (host) of the input URL is preserved in the output [app/utils.py:13]."""
    input_url = "https://cdn.example.test/bucketname/folder/thumb.png"
    result = format_storage_url(input_url)
    assert "cdn.example.test" in result


# ── get_extension_from_mimetype ────────────────────────────────────────────


def test_get_extension_from_mimetype_jpeg():
    """image/jpeg → 'jpg' [app/utils.py:5, 19]."""
    result = get_extension_from_mimetype("image/jpeg")
    assert result == "jpg"  # [app/utils.py:5 MIME_TO_EXTENSION]


def test_get_extension_from_mimetype_png():
    """image/png → 'png' [app/utils.py:4, 19]."""
    result = get_extension_from_mimetype("image/png")
    assert result == "png"  # [app/utils.py:4 MIME_TO_EXTENSION]


def test_get_extension_from_mimetype_unknown_defaults_to_png():
    """Unknown MIME type returns 'png' as the default [app/utils.py:19].

    MIME_TO_EXTENSION.get(mime_type, "png") — default is 'png' [app/utils.py:19].
    """
    result = get_extension_from_mimetype("image/gif")
    assert result == "png"


def test_get_extension_from_mimetype_empty_string_defaults_to_png():
    """Empty string MIME type → default 'png' [app/utils.py:19]."""
    result = get_extension_from_mimetype("")
    assert result == "png"


def test_get_extension_from_mimetype_returns_string():
    """Return type is always str [app/utils.py:17]."""
    result = get_extension_from_mimetype("image/jpeg")
    assert isinstance(result, str)
