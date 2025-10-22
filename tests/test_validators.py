import pytest

from bot.utils.validators import validate_channel_name, validate_scrape_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("@channelname", "@channelname"),
        ("channelname", "@channelname"),
        (" Channel_123 ", "@Channel_123"),
    ],
)
def test_validate_channel_name_returns_canonical_form(raw, expected):
    assert validate_channel_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abcd",  # too short
        "this-channel",  # invalid character
        "https://t.me/s/evil",
        None,
    ],
)
def test_validate_channel_name_rejects_invalid_inputs(raw):
    with pytest.raises(ValueError):
        validate_channel_name(raw)  # type: ignore[arg-type]


def test_validate_scrape_url_returns_expected_https_url():
    assert validate_scrape_url("@keytimebot") == "https://t.me/s/keytimebot"


def test_validate_scrape_url_normalizes_channel_without_at():
    assert validate_scrape_url("keytimebot") == "https://t.me/s/keytimebot"


def test_validate_scrape_url_rejects_urls_disguised_as_channel():
    with pytest.raises(ValueError):
        validate_scrape_url("https://example.com/malicious")
