"""Tests for the Klipsch Flexus media player."""

from __future__ import annotations

from custom_components.klipsch_flexus.media_player import _http_image_url


def test_http_image_url_filters_non_urls():
    # physical inputs report a device skin ref, not a URL → no broken image
    assert _http_image_url("skin:iconHdmi") is None
    assert _http_image_url("") is None
    assert _http_image_url(None) is None
    assert _http_image_url("iconHdmi") is None
    # real artwork URLs pass through
    assert _http_image_url("http://10.0.0.5/art.png") == "http://10.0.0.5/art.png"
    assert _http_image_url("https://art.example/cover.jpg") == "https://art.example/cover.jpg"
