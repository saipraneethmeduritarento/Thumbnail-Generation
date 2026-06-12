"""
Unit tests for app/services/image_variation.py

Functions tested:
  fetch_content_details(content_id)            [app/services/image_variation.py:46-63]
  format_thumbnail_url(content_details)        [app/services/image_variation.py:65-79]
  download_thumbnail(thumbnail_url)            [app/services/image_variation.py:81-105]
  download_content_thumbnail(content_id)       [app/services/image_variation.py:107-124]
  generate_image_variations(content_id)        [app/services/image_variation.py:306-328]

All external I/O (requests, Vertex AI, GCP Storage) is mocked.

Patch targets read from module-level imports in image_variation.py:
  - requests.get           → app.services.image_variation.requests.get [line 6]
  - GenerativeModel        → app.services.image_variation.GenerativeModel [line 14]
  - ImageGenerationModel   → app.services.image_variation.ImageGenerationModel [line 15]
  - storage.write_file     → app.services.image_variation.storage.write_file [line 17]

S8405: no HTTP client calls via TestClient in this file — pure service unit tests.
"""

import pytest
from unittest.mock import MagicMock, patch

# Module-level patches: conftest.py already patched vertexai.init and GCPStorage.__init__
# before app import. These service tests additionally patch the call-site functions.

_REQUESTS_GET = "app.services.image_variation.requests.get"
_GENERATIVE_MODEL = "app.services.image_variation.GenerativeModel"
_IMAGE_GEN_MODEL = "app.services.image_variation.ImageGenerationModel"
_STORAGE_WRITE = "app.services.image_variation.storage.write_file"


# Import the functions under test — safe because conftest.py pre-patches module init
from app.services.image_variation import (
    fetch_content_details,
    format_thumbnail_url,
    download_thumbnail,
    download_content_thumbnail,
    generate_image_variations,
)


# ── fetch_content_details ─────────────────────────────────────────────────


def _make_requests_get_mock(status_code=200, json_data=None):
    """Build a mock for requests.get that returns a response-like object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.raise_for_status.return_value = None  # no-op on success
    return mock_resp


def test_fetch_content_details_happy_path():
    """Happy path: requests.get returns 200, response.json() returns content dict.

    Function URL built as: {KB_API_HOST}/api/content/v1/read/{content_id}?mode=edit
    [app/services/image_variation.py:56]
    """
    expected_data = {"result": {"content": {"posterImage": "/assets/thumb.jpg"}}}
    mock_response = _make_requests_get_mock(json_data=expected_data)

    with patch(_REQUESTS_GET, return_value=mock_response) as mock_get:
        result = fetch_content_details("do-0000000000001")

    assert result == expected_data
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "do-0000000000001" in call_url     # content_id in URL [line 56]
    assert "mode=edit" in call_url            # query param present [line 56]


def test_fetch_content_details_propagates_http_error():
    """requests.raise_for_status() raises → Exception propagates out of function.

    [app/services/image_variation.py:58]
    """
    import requests as req_lib

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = req_lib.HTTPError("404 Client Error")

    with patch(_REQUESTS_GET, return_value=mock_response):
        with pytest.raises(req_lib.HTTPError):
            fetch_content_details("do-nonexistent-00000")


def test_fetch_content_details_returns_json_body():
    """Return value is exactly what response.json() returns [app/services/image_variation.py:59]."""
    payload = {"result": {"content": {"posterImage": "https://example.test/img.jpg"}}}
    mock_response = _make_requests_get_mock(json_data=payload)

    with patch(_REQUESTS_GET, return_value=mock_response):
        result = fetch_content_details("do-0000000000002")

    assert result["result"]["content"]["posterImage"] == "https://example.test/img.jpg"


# ── format_thumbnail_url ──────────────────────────────────────────────────


def test_format_thumbnail_url_extracts_poster_image():
    """format_thumbnail_url reads posterImage from content_details dict.

    content_details["result"]["content"]["posterImage"] [app/services/image_variation.py:75]
    """
    content_details = {
        "result": {
            "content": {
                "posterImage": "https://storage.example.test/bucket/base/thumb.jpg"
            }
        }
    }
    result = format_thumbnail_url(content_details)
    # Must return a string URL
    assert isinstance(result, str)
    assert result.startswith("https://")


def test_format_thumbnail_url_calls_format_storage_url():
    """Delegates to format_storage_url [app/services/image_variation.py:76].

    Patching format_storage_url to verify it is called with the posterImage value.
    """
    poster_img = "https://storage.example.test/bucket/base/thumb.jpg"
    content_details = {"result": {"content": {"posterImage": poster_img}}}

    with patch("app.services.image_variation.format_storage_url", return_value="https://formatted.example.test/img.jpg") as mock_fmt:
        result = format_thumbnail_url(content_details)

    mock_fmt.assert_called_once_with(poster_img)
    assert result == "https://formatted.example.test/img.jpg"


# ── download_thumbnail ────────────────────────────────────────────────────


def _make_image_response_mock(content_type="image/jpeg", chunks=None):
    """Build a mock for requests.get(stream=True) returning image bytes."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.iter_content.return_value = iter(chunks or [b"fake-image-bytes"])
    return mock_resp


def test_download_thumbnail_jpeg_happy_path():
    """Happy path with image/jpeg content-type.

    Returns bytes; iter_content chunks concatenated [app/services/image_variation.py:99-101].
    """
    with patch(_REQUESTS_GET, return_value=_make_image_response_mock("image/jpeg")):
        result = download_thumbnail("https://cdn.example.test/thumb.jpg")

    assert isinstance(result, bytes)
    assert result == b"fake-image-bytes"


def test_download_thumbnail_png_happy_path():
    """Happy path with image/png content-type [app/services/image_variation.py:95]."""
    with patch(_REQUESTS_GET, return_value=_make_image_response_mock("image/png", [b"png-data"])):
        result = download_thumbnail("https://cdn.example.test/thumb.png")

    assert result == b"png-data"


def test_download_thumbnail_unsupported_mimetype_raises():
    """Non-image MIME type → ValueError [app/services/image_variation.py:100-101].

    Only image/png and image/jpeg are supported [app/utils.py:5-6 MIME_TO_EXTENSION].
    Error message: "Image can only be in the following formats: image/png, image/jpeg"
    [app/services/image_variation.py:101]
    """
    with patch(_REQUESTS_GET, return_value=_make_image_response_mock("image/gif")):
        with pytest.raises(ValueError, match="Image can only be in the following formats"):
            download_thumbnail("https://cdn.example.test/thumb.gif")


def test_download_thumbnail_propagates_http_error():
    """requests.raise_for_status() on download raises → propagates [app/services/image_variation.py:97]."""
    import requests as req_lib

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("403 Forbidden")

    with patch(_REQUESTS_GET, return_value=mock_resp):
        with pytest.raises(req_lib.HTTPError):
            download_thumbnail("https://cdn.example.test/forbidden.jpg")


def test_download_thumbnail_concatenates_chunks():
    """Multiple iter_content chunks are concatenated [app/services/image_variation.py:104]."""
    chunks = [b"chunk1-", b"chunk2-", b"chunk3"]
    with patch(_REQUESTS_GET, return_value=_make_image_response_mock("image/jpeg", chunks)):
        result = download_thumbnail("https://cdn.example.test/multi.jpg")

    assert result == b"chunk1-chunk2-chunk3"


# ── download_content_thumbnail ────────────────────────────────────────────


def test_download_content_thumbnail_composes_fetch_and_download():
    """Calls fetch_content_details → format_thumbnail_url → download_thumbnail.

    [app/services/image_variation.py:121-124]
    Returns (thumbnail_url: str, image_bytes: bytes).
    """
    content_details = {
        "result": {"content": {"posterImage": "https://storage.example.test/b/base/thumb.jpg"}}
    }
    formatted_url = "https://cdn.example.test/assets/public/base/thumb.jpg"
    image_bytes = b"image-content"

    with (
        patch("app.services.image_variation.fetch_content_details", return_value=content_details) as mock_fetch,
        patch("app.services.image_variation.format_thumbnail_url", return_value=formatted_url) as mock_fmt,
        patch("app.services.image_variation.download_thumbnail", return_value=image_bytes) as mock_dl,
    ):
        url, data = download_content_thumbnail("do-0000000000003")

    mock_fetch.assert_called_once_with("do-0000000000003")
    mock_fmt.assert_called_once_with(content_details)
    mock_dl.assert_called_once_with(formatted_url)
    assert url == formatted_url
    assert data == image_bytes


# ── generate_image_variations ─────────────────────────────────────────────


def _make_image_obj(mime_type="image/jpeg", data=b"img"):
    """Synthetic image object matching the shape used in generate_image_variations
    [app/services/image_variation.py:309-319]:
      image._mime_type, image._image_bytes
    """
    img = MagicMock()
    img._mime_type = mime_type
    img._image_bytes = data
    return img


def test_generate_image_variations_no_logo():
    """No logos detected → logo_detection.found=False, warning=None.

    [app/services/image_variation.py:306-316]
    """
    image_objects = [_make_image_obj()]
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000004/thumb.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"img-bytes")),
        patch("app.services.image_variation.detect_logos", return_value=[]),  # no logos
        patch("app.services.image_variation.generate_content", return_value="test image prompt"),
        patch("app.services.image_variation.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE),
    ):
        logo, urls = generate_image_variations("do-0000000000004")

    assert logo["found"] is False       # [app/services/image_variation.py:308-310]
    assert logo["warning"] is None      # [app/services/image_variation.py:311]
    assert len(urls) == 1


def test_generate_image_variations_logo_detected():
    """Logo detected → logo_detection.found=True, warning text set.

    [app/services/image_variation.py:312-315]
    """
    logo_result = [{"logo_name": "TestCorp", "confidence_score": 0.95}]
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000005/thumb.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"img-bytes")),
        patch("app.services.image_variation.detect_logos", return_value=logo_result),
        patch("app.services.image_variation.generate_content", return_value="prompt with logo"),
        patch("app.services.image_variation.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        logo, urls = generate_image_variations("do-0000000000005")

    assert logo["found"] is True        # [app/services/image_variation.py:313]
    assert logo["warning"] is not None  # [app/services/image_variation.py:314-315]
    assert "logo" in logo["warning"].lower()


def test_generate_image_variations_returns_correct_url_count():
    """Number of image URLs matches number of images returned by generate_image.

    [app/services/image_variation.py:320-327]
    """
    n_images = 3
    image_objects = [_make_image_obj(data=f"img{i}".encode()) for i in range(n_images)]
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000006/thumb.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"img-bytes")),
        patch("app.services.image_variation.detect_logos", return_value=[]),
        patch("app.services.image_variation.generate_content", return_value="prompt"),
        patch("app.services.image_variation.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-0000000000006")

    assert len(urls) == n_images


def test_generate_image_variations_urls_contain_content_id():
    """Generated URLs contain the content_id and STORAGE_PROXY_PATH.

    URL built as: urljoin(KB_API_HOST, STORAGE_PROXY_PATH / content_id / filename)
    [app/services/image_variation.py:323-324]
    """
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000007/thumb.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"img-bytes")),
        patch("app.services.image_variation.detect_logos", return_value=[]),
        patch("app.services.image_variation.generate_content", return_value="prompt"),
        patch("app.services.image_variation.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-0000000000007")

    assert len(urls) == 1
    assert "do-0000000000007" in urls[0]  # content_id embedded in URL [line 324]


def test_generate_image_variations_calls_storage_write():
    """storage.write_file called once per generated image.

    [app/services/image_variation.py:321]
    """
    n_images = 2
    image_objects = [_make_image_obj() for _ in range(n_images)]
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000008/t.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"img-bytes")),
        patch("app.services.image_variation.detect_logos", return_value=[]),
        patch("app.services.image_variation.generate_content", return_value="p"),
        patch("app.services.image_variation.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE) as mock_write,
    ):
        generate_image_variations("do-0000000000008")

    assert mock_write.call_count == n_images  # one write per image [line 321]


def test_generate_image_variations_no_sensitive_data_in_urls():
    """Generated URLs must not contain credentials, passwords, or internal secrets [OWASP A05]."""
    thumbnail_url = "https://cdn.example.test/assets/public/do-0000000000009/t.jpg"

    with (
        patch("app.services.image_variation.download_content_thumbnail",
              return_value=(thumbnail_url, b"bytes")),
        patch("app.services.image_variation.detect_logos", return_value=[]),
        patch("app.services.image_variation.generate_content", return_value="p"),
        patch("app.services.image_variation.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-0000000000009")

    for url in urls:
        assert "password" not in url.lower()
        assert "secret" not in url.lower()
        assert "credential" not in url.lower()
