"""
Unit tests for app/utils.py

Functions tested:
  format_storage_url(image_url, asset_prefix)  [app/utils.py:28-33]
  get_extension_from_mimetype(mime_type)        [app/utils.py:52-54]
  get_file_extension(file_path)                 [app/utils.py:35-46]
  get_file_mimetype(file_path)                  [app/utils.py:48-50]

These are pure functions with no external dependencies — no mocks required.
S8405: no HTTP calls in this test file.
"""

from app.utils import (
    format_storage_url,
    get_extension_from_mimetype,
    get_file_extension,
    get_file_mimetype,
    ASSET_PREFIX,
    DEFAULT_EXTENSION,
    DEFAULT_MIME_TYPE,
)


# -- format_storage_url -------------------------------------------------------


def test_format_storage_url_standard_gcs_url():
    """Happy path: GCS-style URL converted to public HTTPS asset URL.

    Input URL structure: <scheme>://<bucket>/<prefix>/<filename>
    Expected: https://<bucket>/assets/public/<filename>
    [app/utils.py:28-33]
    """
    input_url = "https://storage.googleapis.com/bucket-name/thumbnail.jpg"
    result = format_storage_url(input_url)
    assert result.startswith("https://")
    assert "storage.googleapis.com" in result
    assert ASSET_PREFIX.strip("/") in result


def test_format_storage_url_uses_default_asset_prefix():
    """format_storage_url uses ASSET_PREFIX constant as default [app/utils.py:5, 28]."""
    input_url = "https://storage.example.test/bucket/path/to/image.png"
    result = format_storage_url(input_url)
    assert "/assets/public/" in result


def test_format_storage_url_custom_asset_prefix():
    """Custom asset_prefix overrides the default [app/utils.py:28]."""
    input_url = "https://storage.example.test/bucket/segment1/segment2/image.jpg"
    result = format_storage_url(input_url, asset_prefix="/custom/prefix/")
    assert "/custom/prefix/" in result


def test_format_storage_url_returns_string():
    """Return type must be str [app/utils.py:28]."""
    result = format_storage_url("https://storage.example.test/b/a/b/c.jpg")
    assert isinstance(result, str)


def test_format_storage_url_https_scheme():
    """Output URL always starts with https:// [app/utils.py:31].

    The function hardcodes 'https' + '://' regardless of the input scheme.
    """
    result = format_storage_url("http://storage.example.test/bucket/path/img.jpg")
    assert result.startswith("https://")


def test_format_storage_url_preserves_netloc():
    """Network location (host) of the input URL is preserved in the output [app/utils.py:31]."""
    input_url = "https://cdn.example.test/bucketname/folder/thumb.png"
    result = format_storage_url(input_url)
    assert "cdn.example.test" in result


# -- get_extension_from_mimetype ----------------------------------------------


def test_get_extension_from_mimetype_jpeg():
    """image/jpeg -> 'jpg' [app/utils.py:52-54]."""
    assert get_extension_from_mimetype("image/jpeg") == "jpg"


def test_get_extension_from_mimetype_png():
    """image/png -> 'png' [app/utils.py:52-54]."""
    assert get_extension_from_mimetype("image/png") == "png"


def test_get_extension_from_mimetype_unknown_defaults_to_png():
    """Unknown MIME type returns 'png' as the default [app/utils.py:54]."""
    assert get_extension_from_mimetype("image/gif") == "png"


def test_get_extension_from_mimetype_empty_string_defaults_to_png():
    """Empty string MIME type -> default 'png' [app/utils.py:54]."""
    assert get_extension_from_mimetype("") == "png"


def test_get_extension_from_mimetype_returns_string():
    """Return type is always str [app/utils.py:52]."""
    assert isinstance(get_extension_from_mimetype("image/jpeg"), str)


# -- get_file_extension -------------------------------------------------------


def test_get_file_extension_jpg():
    """Standard .jpg URL returns 'jpg' [app/utils.py:41]."""
    assert get_file_extension("https://storage.example.test/bucket/image.jpg") == "jpg"


def test_get_file_extension_jpeg():
    """Standard .jpeg URL returns 'jpeg' [app/utils.py:41]."""
    assert get_file_extension("https://storage.example.test/bucket/photo.jpeg") == "jpeg"


def test_get_file_extension_png():
    """Standard .png URL returns 'png' [app/utils.py:41]."""
    assert get_file_extension("https://storage.example.test/bucket/image.png") == "png"


def test_get_file_extension_uppercase_normalised():
    """Extension is lowercased [app/utils.py:41]."""
    assert get_file_extension("https://storage.example.test/IMAGE.JPG") == "jpg"


def test_get_file_extension_no_extension_returns_default():
    """Path with no extension returns DEFAULT_EXTENSION [app/utils.py:41]."""
    assert get_file_extension("https://storage.example.test/bucket/imagefile") == DEFAULT_EXTENSION


def test_get_file_extension_empty_string_returns_default():
    """Empty string — urlparse path is empty, falls back to DEFAULT_EXTENSION [app/utils.py:43]."""
    assert get_file_extension("") == DEFAULT_EXTENSION


def test_get_file_extension_returns_string():
    """Return type is always str [app/utils.py:35]."""
    assert isinstance(get_file_extension("https://storage.example.test/img.png"), str)


# -- get_file_mimetype --------------------------------------------------------


def test_get_file_mimetype_jpg_url():
    """JPG URL returns 'image/jpeg' [app/utils.py:48-50]."""
    assert get_file_mimetype("https://storage.example.test/bucket/image.jpg") == "image/jpeg"


def test_get_file_mimetype_png_url():
    """PNG URL returns 'image/png' [app/utils.py:48-50]."""
    assert get_file_mimetype("https://storage.example.test/bucket/image.png") == "image/png"


def test_get_file_mimetype_unknown_extension_returns_default():
    """Unknown extension returns DEFAULT_MIME_TYPE [app/utils.py:50]."""
    assert get_file_mimetype("https://storage.example.test/bucket/file.bmp") == DEFAULT_MIME_TYPE


def test_get_file_mimetype_returns_string():
    """Return type is always str [app/utils.py:48]."""
    assert isinstance(get_file_mimetype("https://storage.example.test/img.jpg"), str)


def test_get_file_extension_exception_path_returns_default():
    """get_file_extension catches any Exception and returns DEFAULT_EXTENSION [app/utils.py:44-46].

    urlparse itself won't raise, but the path inside the try can be forced to
    raise by passing a non-string type that causes os.path.splitext to fail.
    """
    from unittest.mock import patch
    with patch("app.utils.urlparse", side_effect=Exception("forced parse error")):
        result = get_file_extension("https://storage.example.test/image.jpg")
    assert result == DEFAULT_EXTENSION
