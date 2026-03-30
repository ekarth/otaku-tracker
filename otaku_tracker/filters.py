from datetime import datetime

from .models import MediaType, ReadlistEntry


def progress_text(entry: ReadlistEntry) -> str:
    if entry.series.media_type == MediaType.MOVIE:
        return "—"

    if entry.series.media_type == MediaType.ANIME:
        watched_parts = []
        if entry.seasons_watched is not None:
            watched_parts.append(f"S {entry.seasons_watched}")
        if entry.current_episode is not None:
            watched_parts.append(f"Ep {entry.current_episode}")
        watched = " | ".join(watched_parts) if watched_parts else "Not started"

        total_parts = []
        if entry.series.seasons_aired is not None:
            total_parts.append(f"S {entry.series.seasons_aired}")
        if entry.series.latest_episode is not None:
            total_parts.append(f"Ep {entry.series.latest_episode}")
        total = f"/ {' | '.join(total_parts)}" if total_parts else ""
        return f"{watched} {total}".strip()

    parts = []
    if entry.current_volume is not None:
        parts.append(f"Vol {entry.current_volume}")
    if not parts:
        return "Not started"

    target = []
    if entry.series.latest_volume is not None:
        target.append(f"Vol {entry.series.latest_volume}")
    target_text = f" / {' | '.join(target)}" if target else ""
    return f"{' | '.join(parts)}{target_text}"


def downloaded_text(entry: ReadlistEntry) -> str:
    if entry.series.media_type in (MediaType.ANIME, MediaType.MOVIE):
        return "—"

    if not entry.prefer_download:
        return "Streaming / online"

    parts = []
    if entry.downloaded_volume_upto is not None:
        parts.append(f"Vol {entry.downloaded_volume_upto}")
    if not parts:
        return "No volumes downloaded"
    return f"Downloaded up to {' | '.join(parts)}"


def datetime_filter(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def register_filters(app) -> None:
    app.add_template_filter(progress_text, "progress_text")
    app.add_template_filter(downloaded_text, "downloaded_text")
    app.add_template_filter(datetime_filter, "dt")
