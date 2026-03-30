from datetime import date
from decimal import Decimal, InvalidOperation

from .extensions import db
from .models import (
    HistoryEvent,
    HistoryEventType,
    ListStatus,
    MediaType,
    ReadlistEntry,
    Series,
)


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.upper()


def validate_media_specific_values(
    media_type: MediaType,
    volume_value: int | None,
    episode_value: int | None,
    volume_label: str,
    episode_label: str,
) -> str | None:
    if media_type in (MediaType.BOOK, MediaType.MOVIE) and episode_value is not None:
        return f"{episode_label} is only allowed for anime."
    if media_type in (MediaType.ANIME, MediaType.MOVIE) and volume_value is not None:
        return f"{volume_label} is only allowed for books."
    return None


def validate_anime_only_value(media_type: MediaType, value: int | None, label: str) -> str | None:
    if media_type in (MediaType.BOOK, MediaType.MOVIE) and value is not None:
        return f"{label} is only allowed for anime."
    return None


def validate_download_options(
    media_type: MediaType,
    prefer_download: bool,
    downloaded_volume_upto: int | None,
) -> str | None:
    if media_type in (MediaType.ANIME, MediaType.MOVIE):
        if prefer_download or downloaded_volume_upto is not None:
            return "Download options are only available for books."
    return None


def validate_parent_anime(media_type: MediaType, parent_anime_id: int | None) -> str | None:
    if parent_anime_id is None:
        return None
    if media_type != MediaType.MOVIE:
        return "Parent anime link is only allowed for movies."
    parent = db.session.get(Series, parent_anime_id)
    if parent is None:
        return "The specified parent anime does not exist."
    if parent.media_type != MediaType.ANIME:
        return "The parent series must be an anime."
    return None


def add_history_event(
    entry: ReadlistEntry,
    event_type: HistoryEventType,
    old_status: ListStatus | None = None,
    new_status: ListStatus | None = None,
    volume: int | None = None,
    episode: int | None = None,
    details: str | None = None,
) -> None:
    db.session.add(
        HistoryEvent(
            entry=entry,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            volume=volume,
            episode=episode,
            details=details,
        )
    )
