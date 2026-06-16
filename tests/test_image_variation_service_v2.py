"""
Unit tests for app/services/v2/image_variation.py

Functions tested:
  fetch_content_details(content_id)                     [app/services/v2/image_variation.py]
  format_thumbnail_url(content_details)                 [app/services/v2/image_variation.py]
  download_content_thumbnail(content_id)                [app/services/v2/image_variation.py]
  generate_image_variations(content_id)                 [app/services/v2/image_variation.py]

Key differences from v1:
  - download_content_thumbnail returns str (URL only), not (url, bytes) tuple
  - detect_logos(image_url, image_mimetype) — uses GCS URI, not bytes
  - generate_content(image_url, image_mimetype) — uses GCS URI, not bytes
  - filenames include timestamp: ai_{timestamp}_{stem}_{index}.{ext}
  - get_file_mimetype used to resolve mimetype from URL

All external I/O (requests, Vertex AI, GCP Storage) is mocked.
"""

import pytest
from unittest.mock import MagicMock, patch

_MODULE = "app.services.v2.image_variation"
_REQUESTS_GET = f"{_MODULE}.requests.get"
_STORAGE_WRITE = f"{_MODULE}.storage.write_file"
_GET_FILE_MIMETYPE = f"{_MODULE}.get_file_mimetype"

from app.services.v2.image_variation import (
    fetch_content_details,
    format_thumbnail_url,
    download_content_thumbnail,
    generate_image_variations,
    detect_logos,
    generate_content,
    generate_image,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_requests_get_mock(status_code=200, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_image_obj(mime_type="image/jpeg", data=b"img"):
    img = MagicMock()
    img._mime_type = mime_type
    img._image_bytes = data
    return img


# ── fetch_content_details ─────────────────────────────────────────────────


def test_v2_fetch_content_details_happy_path():
    """Happy path: 200 response with expected JSON body."""
    expected_data = {"result": {"content": {"posterImage": "/assets/thumb.jpg"}}}
    mock_response = _make_requests_get_mock(json_data=expected_data)

    with patch(_REQUESTS_GET, return_value=mock_response) as mock_get:
        result = fetch_content_details("do-v2-0000000001")

    assert result == expected_data
    call_url = mock_get.call_args[0][0]
    assert "do-v2-0000000001" in call_url
    assert "mode=edit" in call_url


def test_v2_fetch_content_details_propagates_http_error():
    """raise_for_status() raises → propagates."""
    import requests as req_lib

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = req_lib.HTTPError("404 Not Found")

    with patch(_REQUESTS_GET, return_value=mock_response):
        with pytest.raises(req_lib.HTTPError):
            fetch_content_details("do-v2-nonexistent")


def test_v2_fetch_content_details_returns_json_body():
    """Return value is exactly what response.json() returns."""
    payload = {"result": {"content": {"posterImage": "https://example.test/img.jpg"}}}
    mock_response = _make_requests_get_mock(json_data=payload)

    with patch(_REQUESTS_GET, return_value=mock_response):
        result = fetch_content_details("do-v2-0000000002")

    assert result["result"]["content"]["posterImage"] == "https://example.test/img.jpg"


# ── format_thumbnail_url ──────────────────────────────────────────────────


def test_v2_format_thumbnail_url_extracts_poster_image():
    """Reads posterImage and delegates to format_storage_url."""
    poster_img = "https://storage.example.test/bucket/base/thumb.jpg"
    content_details = {"result": {"content": {"posterImage": poster_img}}}

    with patch(f"{_MODULE}.format_storage_url", return_value="https://cdn.example.test/thumb.jpg") as mock_fmt:
        result = format_thumbnail_url(content_details)

    mock_fmt.assert_called_once_with(poster_img)
    assert result == "https://cdn.example.test/thumb.jpg"


# ── download_content_thumbnail ────────────────────────────────────────────


def test_v2_download_content_thumbnail_returns_url_only():
    """v2 returns str URL, not (url, bytes) tuple."""
    content_details = {
        "result": {"content": {"posterImage": "https://storage.example.test/b/base/thumb.jpg"}}
    }
    formatted_url = "https://cdn.example.test/assets/public/base/thumb.jpg"

    with (
        patch(f"{_MODULE}.fetch_content_details", return_value=content_details),
        patch(f"{_MODULE}.format_thumbnail_url", return_value=formatted_url),
    ):
        result = download_content_thumbnail("do-v2-0000000003")

    assert isinstance(result, str)
    assert result == formatted_url


def test_v2_download_content_thumbnail_calls_fetch_and_format():
    """fetch_content_details and format_thumbnail_url are called with correct args."""
    content_details = {"result": {"content": {"posterImage": "https://x.test/img.jpg"}}}
    formatted_url = "https://cdn.example.test/img.jpg"

    with (
        patch(f"{_MODULE}.fetch_content_details", return_value=content_details) as mock_fetch,
        patch(f"{_MODULE}.format_thumbnail_url", return_value=formatted_url) as mock_fmt,
    ):
        download_content_thumbnail("do-v2-0000000004")

    mock_fetch.assert_called_once_with("do-v2-0000000004")
    mock_fmt.assert_called_once_with(content_details)


# ── generate_image_variations ─────────────────────────────────────────────


def test_v2_generate_image_variations_no_logo():
    """No logos → logo_detection.found=False, warning=None."""
    image_objects = [_make_image_obj()]
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000005/thumb.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="test prompt"),
        patch(f"{_MODULE}.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE),
    ):
        logo, urls = generate_image_variations("do-v2-0000000005")

    assert logo["found"] is False
    assert logo["warning"] is None
    assert len(urls) == 1


def test_v2_generate_image_variations_logo_detected():
    """Logo detected → found=True, warning contains 'logo'."""
    logo_result = [{"logo_name": "TestCorp", "confidence_score": 0.95}]
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000006/thumb.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=logo_result),
        patch(f"{_MODULE}.generate_content", return_value="prompt with logo"),
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        logo, urls = generate_image_variations("do-v2-0000000006")

    assert logo["found"] is True
    assert logo["warning"] is not None
    assert "logo" in logo["warning"].lower()


def test_v2_generate_image_variations_detect_logos_receives_url_and_mimetype():
    """detect_logos is called with (image_url, file_mimetype) — v2 API, not bytes."""
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000007/thumb.jpg"
    mimetype = "image/jpeg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value=mimetype),
        patch(f"{_MODULE}.detect_logos", return_value=[]) as mock_detect,
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        generate_image_variations("do-v2-0000000007")

    mock_detect.assert_called_once_with(thumbnail_url, mimetype)


def test_v2_generate_image_variations_generate_content_receives_url_and_mimetype():
    """generate_content is called with (image_url, file_mimetype) — v2 API, not bytes."""
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000008/thumb.jpg"
    mimetype = "image/png"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value=mimetype),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p") as mock_gen_content,
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        generate_image_variations("do-v2-0000000008")

    mock_gen_content.assert_called_once_with(thumbnail_url, mimetype)


def test_v2_generate_image_variations_returns_correct_url_count():
    """Number of returned URLs matches number of generated images."""
    n_images = 3
    image_objects = [_make_image_obj(data=f"img{i}".encode()) for i in range(n_images)]
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000009/thumb.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-v2-0000000009")

    assert len(urls) == n_images


def test_v2_generate_image_variations_urls_contain_content_id():
    """Generated URLs contain the content_id."""
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000010/thumb.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-v2-0000000010")

    assert all("do-v2-0000000010" in url for url in urls)


def test_v2_generate_image_variations_filename_includes_ai_prefix():
    """v2 filenames start with 'ai_' (includes timestamp prefix)."""
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000011/thumb.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE) as mock_write,
    ):
        generate_image_variations("do-v2-0000000011")

    written_path = mock_write.call_args[0][0]
    filename = written_path.split("/")[-1]
    assert filename.startswith("ai_")


def test_v2_generate_image_variations_calls_storage_write_once_per_image():
    """storage.write_file called exactly once per generated image."""
    n_images = 2
    image_objects = [_make_image_obj() for _ in range(n_images)]
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000012/t.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=image_objects),
        patch(_STORAGE_WRITE) as mock_write,
    ):
        generate_image_variations("do-v2-0000000012")

    assert mock_write.call_count == n_images


def test_v2_generate_image_variations_no_sensitive_data_in_urls():
    """Generated URLs must not contain credentials or secrets [OWASP A05]."""
    thumbnail_url = "https://storage.googleapis.com/bucket/do-v2-0000000013/t.jpg"

    with (
        patch(f"{_MODULE}.download_content_thumbnail", return_value=thumbnail_url),
        patch(_GET_FILE_MIMETYPE, return_value="image/jpeg"),
        patch(f"{_MODULE}.detect_logos", return_value=[]),
        patch(f"{_MODULE}.generate_content", return_value="p"),
        patch(f"{_MODULE}.generate_image", return_value=[_make_image_obj()]),
        patch(_STORAGE_WRITE),
    ):
        _, urls = generate_image_variations("do-v2-0000000013")

    for url in urls:
        assert "password" not in url.lower()
        assert "secret" not in url.lower()
        assert "credential" not in url.lower()


# ── detect_logos ───────────────────────────────────────────────────────────

_GENERATIVE_MODEL = f"{_MODULE}.GenerativeModel"
_PART = f"{_MODULE}.Part"


def test_detect_logos_returns_parsed_json():
    """detect_logos calls model.generate_content and json.loads the response [image_variation.py:100-124]."""
    logo_data = [{"logo_name": "TestCorp", "position": {"x": 0, "y": 0, "width": 100, "height": 50}, "confidence_score": 0.9}]

    mock_response = MagicMock()
    mock_response.text = '[{"logo_name": "TestCorp", "position": {"x": 0, "y": 0, "width": 100, "height": 50}, "confidence_score": 0.9}]'
    mock_response.usage_metadata = MagicMock()

    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.return_value = mock_response

    mock_image_part = MagicMock()
    mock_text_part = MagicMock()

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_model_instance) as mock_gm,
        patch(_PART + ".from_uri", return_value=mock_image_part),
        patch(_PART + ".from_text", return_value=mock_text_part),
    ):
        result = detect_logos("https://storage.googleapis.com/bucket/img.jpg", "image/jpeg")

    assert isinstance(result, list)
    assert result[0]["logo_name"] == "TestCorp"
    mock_model_instance.generate_content.assert_called_once()


def test_detect_logos_no_logos_returns_empty_list():
    """detect_logos returns empty list when model finds no logos [image_variation.py:100-124]."""
    mock_response = MagicMock()
    mock_response.text = "[]"
    mock_response.usage_metadata = MagicMock()

    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.return_value = mock_response

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_model_instance),
        patch(_PART + ".from_uri", return_value=MagicMock()),
        patch(_PART + ".from_text", return_value=MagicMock()),
    ):
        result = detect_logos("https://storage.googleapis.com/bucket/img.png", "image/png")

    assert result == []


def test_detect_logos_passes_correct_mime_type_to_part():
    """Part.from_uri is called with the provided mime_type [image_variation.py:105]."""
    mock_response = MagicMock()
    mock_response.text = "[]"
    mock_response.usage_metadata = MagicMock()

    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.return_value = mock_response

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_model_instance),
        patch(_PART + ".from_uri", return_value=MagicMock()) as mock_from_uri,
        patch(_PART + ".from_text", return_value=MagicMock()),
    ):
        detect_logos("https://storage.googleapis.com/bucket/img.jpeg", "image/jpeg")

    mock_from_uri.assert_called_once_with(
        uri="https://storage.googleapis.com/bucket/img.jpeg",
        mime_type="image/jpeg",
    )


# ── generate_content ───────────────────────────────────────────────────────


def test_generate_content_returns_model_response_text():
    """generate_content calls gemini.generate_content and returns response.text [image_variation.py:162-175]."""
    mock_response = MagicMock()
    mock_response.text = "A scenic landscape with mountains and a river."
    mock_response.usage_metadata = MagicMock()

    mock_gemini_instance = MagicMock()
    mock_gemini_instance.generate_content.return_value = mock_response

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_gemini_instance),
        patch(_PART + ".from_uri", return_value=MagicMock()),
        patch(_PART + ".from_text", return_value=MagicMock()),
        patch(f"{_MODULE}.GenerationConfig", return_value=MagicMock()),
    ):
        result = generate_content("https://storage.googleapis.com/bucket/img.jpg", "image/jpeg")

    assert result == "A scenic landscape with mountains and a river."
    mock_gemini_instance.generate_content.assert_called_once()


def test_generate_content_passes_correct_mime_type():
    """Part.from_uri is called with the correct image_mimetype [image_variation.py:167-168]."""
    mock_response = MagicMock()
    mock_response.text = "some prompt text"
    mock_response.usage_metadata = MagicMock()

    mock_gemini_instance = MagicMock()
    mock_gemini_instance.generate_content.return_value = mock_response

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_gemini_instance),
        patch(_PART + ".from_uri", return_value=MagicMock()) as mock_from_uri,
        patch(_PART + ".from_text", return_value=MagicMock()),
        patch(f"{_MODULE}.GenerationConfig", return_value=MagicMock()),
    ):
        generate_content("https://storage.googleapis.com/bucket/photo.png", "image/png")

    mock_from_uri.assert_called_once_with(
        uri="https://storage.googleapis.com/bucket/photo.png",
        mime_type="image/png",
    )


def test_generate_content_returns_string():
    """Return type of generate_content is str [image_variation.py:179]."""
    mock_response = MagicMock()
    mock_response.text = "generated text"
    mock_response.usage_metadata = MagicMock()

    mock_gemini_instance = MagicMock()
    mock_gemini_instance.generate_content.return_value = mock_response

    with (
        patch(_GENERATIVE_MODEL, return_value=mock_gemini_instance),
        patch(_PART + ".from_uri", return_value=MagicMock()),
        patch(_PART + ".from_text", return_value=MagicMock()),
        patch(f"{_MODULE}.GenerationConfig", return_value=MagicMock()),
    ):
        result = generate_content("https://cdn.example.test/img.jpg", "image/jpeg")

    assert isinstance(result, str)


# ── generate_image ─────────────────────────────────────────────────────────

_IMAGE_GEN_MODEL = f"{_MODULE}.ImageGenerationModel"


def test_generate_image_calls_from_pretrained_with_vision_model():
    """ImageGenerationModel.from_pretrained is called with VISION_MODEL [image_variation.py:184]."""
    mock_images = MagicMock()
    mock_model_instance = MagicMock()
    mock_model_instance.generate_images.return_value = mock_images

    with patch(_IMAGE_GEN_MODEL) as mock_igm:
        mock_igm.from_pretrained.return_value = mock_model_instance
        result = generate_image("a beautiful landscape")

    mock_igm.from_pretrained.assert_called_once()
    mock_model_instance.generate_images.assert_called_once()
    assert result is mock_images


def test_generate_image_passes_prompt():
    """generate_images is called with the provided prompt [image_variation.py:185-191]."""
    mock_model_instance = MagicMock()
    mock_model_instance.generate_images.return_value = MagicMock()

    with patch(_IMAGE_GEN_MODEL) as mock_igm:
        mock_igm.from_pretrained.return_value = mock_model_instance
        generate_image("mountains and rivers")

    call_kwargs = mock_model_instance.generate_images.call_args
    assert call_kwargs[1]["prompt"] == "mountains and rivers"


def test_generate_image_returns_generation_response():
    """Return value is the ImageGenerationResponse from generate_images [image_variation.py:191]."""
    expected_response = MagicMock()
    mock_model_instance = MagicMock()
    mock_model_instance.generate_images.return_value = expected_response

    with patch(_IMAGE_GEN_MODEL) as mock_igm:
        mock_igm.from_pretrained.return_value = mock_model_instance
        result = generate_image("test prompt")

    assert result is expected_response
