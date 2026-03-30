"""Unit tests for validation and parsing utilities."""
import pytest

from otaku_tracker.models import MediaType
from otaku_tracker.utils import (
    normalize_title,
    parse_date,
    parse_decimal,
    parse_int,
    validate_anime_only_value,
    validate_download_options,
    validate_media_specific_values,
)


class TestParseInt:
    def test_valid_integer(self):
        assert parse_int("5") == 5

    def test_whitespace_trimmed(self):
        assert parse_int("  10  ") == 10

    def test_empty_string_returns_none(self):
        assert parse_int("") is None

    def test_none_returns_none(self):
        assert parse_int(None) is None

    def test_non_numeric_returns_none(self):
        assert parse_int("abc") is None


class TestParseDecimal:
    def test_integer_string(self):
        from decimal import Decimal
        assert parse_decimal("3") == Decimal("3")

    def test_fractional(self):
        from decimal import Decimal
        assert parse_decimal("1.5") == Decimal("1.5")

    def test_none_returns_none(self):
        assert parse_decimal(None) is None

    def test_empty_returns_none(self):
        assert parse_decimal("") is None

    def test_invalid_returns_none(self):
        assert parse_decimal("abc") is None


class TestParseDate:
    def test_valid_iso_date(self):
        from datetime import date
        assert parse_date("2024-01-15") == date(2024, 1, 15)

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_empty_returns_none(self):
        assert parse_date("") is None

    def test_invalid_returns_none(self):
        assert parse_date("not-a-date") is None


class TestNormalizeTitle:
    def test_uppercases(self):
        assert normalize_title("naruto") == "NARUTO"

    def test_strips_whitespace(self):
        assert normalize_title("  one piece  ") == "ONE PIECE"

    def test_none_returns_none(self):
        assert normalize_title(None) is None

    def test_blank_string_returns_none(self):
        assert normalize_title("   ") is None


class TestValidateMediaSpecificValues:
    def test_book_with_episode_is_error(self):
        err = validate_media_specific_values(MediaType.BOOK, None, 5, "Latest volume", "Latest episode")
        assert err is not None
        assert "anime" in err.lower()

    def test_anime_with_volume_is_error(self):
        err = validate_media_specific_values(MediaType.ANIME, 3, None, "Latest volume", "Latest episode")
        assert err is not None
        assert "books" in err.lower()

    def test_movie_with_episode_is_error(self):
        err = validate_media_specific_values(MediaType.MOVIE, None, 1, "Latest volume", "Latest episode")
        assert err is not None

    def test_movie_with_volume_is_error(self):
        err = validate_media_specific_values(MediaType.MOVIE, 1, None, "Latest volume", "Latest episode")
        assert err is not None

    def test_book_with_volume_ok(self):
        assert validate_media_specific_values(MediaType.BOOK, 5, None, "Latest volume", "Latest episode") is None

    def test_anime_with_episode_ok(self):
        assert validate_media_specific_values(MediaType.ANIME, None, 12, "Latest volume", "Latest episode") is None

    def test_movie_with_neither_ok(self):
        assert validate_media_specific_values(MediaType.MOVIE, None, None, "Latest volume", "Latest episode") is None


class TestValidateAnimeOnlyValue:
    def test_book_with_seasons_is_error(self):
        err = validate_anime_only_value(MediaType.BOOK, 2, "Seasons aired")
        assert err is not None

    def test_movie_with_seasons_is_error(self):
        err = validate_anime_only_value(MediaType.MOVIE, 2, "Seasons aired")
        assert err is not None

    def test_anime_with_seasons_ok(self):
        assert validate_anime_only_value(MediaType.ANIME, 2, "Seasons aired") is None

    def test_none_value_always_ok(self):
        assert validate_anime_only_value(MediaType.BOOK, None, "Seasons aired") is None
        assert validate_anime_only_value(MediaType.MOVIE, None, "Seasons aired") is None


class TestValidateDownloadOptions:
    def test_anime_prefer_download_is_error(self):
        err = validate_download_options(MediaType.ANIME, True, None)
        assert err is not None

    def test_movie_prefer_download_is_error(self):
        err = validate_download_options(MediaType.MOVIE, True, None)
        assert err is not None

    def test_anime_downloaded_vol_is_error(self):
        err = validate_download_options(MediaType.ANIME, False, 5)
        assert err is not None

    def test_book_prefer_download_ok(self):
        assert validate_download_options(MediaType.BOOK, True, 3) is None

    def test_anime_no_downloads_ok(self):
        assert validate_download_options(MediaType.ANIME, False, None) is None

    def test_movie_no_downloads_ok(self):
        assert validate_download_options(MediaType.MOVIE, False, None) is None
