from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import and_, or_

from ..extensions import db
from ..models import (
    BookType,
    DownloadedAsset,
    HistoryEventType,
    ListStatus,
    MediaType,
    PublicationStatus,
    ReadlistEntry,
    Series,
    UnitType,
)
from ..utils import (
    add_history_event,
    normalize_title,
    parse_date,
    parse_decimal,
    parse_int,
    validate_anime_only_value,
    validate_download_options,
    validate_media_specific_values,
    validate_parent_anime,
)

bp = Blueprint("entries", __name__)


@bp.post("/add")
def add_entry():
    japanese_title = normalize_title(request.form.get("japanese_title"))
    english_title = normalize_title(request.form.get("english_title"))
    if not japanese_title and not english_title:
        flash("Provide at least one title (Japanese or English).", "error")
        return redirect(url_for("main.home"))

    media_raw = (request.form.get("media_type") or "").upper()
    if media_raw not in MediaType.__members__:
        flash("Invalid media type.", "error")
        return redirect(url_for("main.home"))
    media_type = MediaType[media_raw]

    if media_type == MediaType.BOOK:
        book_raw = (request.form.get("book_type") or "").upper()
        if book_raw not in BookType.__members__ or book_raw == BookType.N_A.value:
            flash("Choose MANGA, MANHWA, or LIGHT_NOVEL for books.", "error")
            return redirect(url_for("main.home"))
        book_type = BookType[book_raw]
    else:
        book_type = BookType.N_A

    pub_raw = (request.form.get("publication_status") or "ONGOING").upper()
    publication_status = PublicationStatus[pub_raw] if pub_raw in PublicationStatus.__members__ else PublicationStatus.ONGOING
    latest_volume = parse_int(request.form.get("latest_volume"))
    latest_episode = parse_int(request.form.get("latest_episode"))
    seasons_aired = parse_int(request.form.get("seasons_aired"))
    current_volume = parse_int(request.form.get("current_volume"))
    current_episode = parse_int(request.form.get("current_episode"))
    seasons_watched = parse_int(request.form.get("seasons_watched"))
    downloaded_volume_upto = parse_int(request.form.get("downloaded_volume_upto"))
    prefer_download = request.form.get("prefer_download") == "on"
    parent_anime_id = parse_int(request.form.get("parent_anime_id"))

    invalid_message = (
        validate_media_specific_values(media_type, latest_volume, latest_episode, "Latest volume", "Latest episode")
        or validate_anime_only_value(media_type, seasons_aired, "Seasons aired")
        or validate_media_specific_values(media_type, current_volume, current_episode, "Current volume", "Current episode")
        or validate_anime_only_value(media_type, seasons_watched, "Seasons watched")
        or validate_download_options(media_type, prefer_download, downloaded_volume_upto)
        or validate_parent_anime(media_type, parent_anime_id)
    )
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("main.home"))

    series_query = Series.query.filter_by(media_type=media_type, book_type=book_type)
    if japanese_title and english_title:
        series = series_query.filter_by(japanese_title=japanese_title, english_title=english_title).first()
        if series is None:
            series = series_query.filter(
                or_(
                    and_(Series.japanese_title == japanese_title, Series.english_title.is_(None)),
                    and_(Series.english_title == english_title, Series.japanese_title.is_(None)),
                )
            ).first()
    elif japanese_title:
        series = series_query.filter(Series.japanese_title == japanese_title).first()
    else:
        series = series_query.filter(Series.english_title == english_title).first()

    if series is None:
        series = Series(
            japanese_title=japanese_title,
            english_title=english_title,
            media_type=media_type,
            book_type=book_type,
            publication_status=publication_status,
            latest_volume=latest_volume if media_type == MediaType.BOOK else None,
            latest_episode=latest_episode if media_type == MediaType.ANIME else None,
            seasons_aired=seasons_aired if media_type == MediaType.ANIME else None,
            parent_anime_id=parent_anime_id if media_type == MediaType.MOVIE else None,
        )
        db.session.add(series)
        db.session.flush()
    else:
        if japanese_title and not series.japanese_title:
            series.japanese_title = japanese_title
        if english_title and not series.english_title:
            series.english_title = english_title
        series.publication_status = publication_status
        if media_type == MediaType.BOOK and latest_volume is not None:
            series.latest_volume = latest_volume
        if media_type == MediaType.ANIME and latest_episode is not None:
            series.latest_episode = latest_episode
        if media_type == MediaType.ANIME and seasons_aired is not None:
            series.seasons_aired = seasons_aired
        if media_type == MediaType.MOVIE and parent_anime_id is not None:
            series.parent_anime_id = parent_anime_id

    if ReadlistEntry.query.filter_by(series_id=series.id).first() is not None:
        flash("This series is already in your tracker.", "error")
        db.session.rollback()
        return redirect(url_for("main.home"))

    status_raw = (request.form.get("list_status") or "PLANNED").upper()
    list_status = ListStatus[status_raw] if status_raw in ListStatus.__members__ else ListStatus.PLANNED
    today = date.today()

    entry = ReadlistEntry(
        series=series,
        list_status=list_status,
        prefer_download=prefer_download if media_type == MediaType.BOOK else False,
        current_volume=current_volume if media_type == MediaType.BOOK else None,
        current_episode=current_episode if media_type == MediaType.ANIME else None,
        seasons_watched=seasons_watched if media_type == MediaType.ANIME else None,
        downloaded_volume_upto=downloaded_volume_upto if media_type == MediaType.BOOK else None,
        start_date=parse_date(request.form.get("start_date")),
        finish_date=parse_date(request.form.get("finish_date")),
        notes=(request.form.get("notes") or "").strip() or None,
        last_activity_at=datetime.utcnow(),
    )

    if entry.list_status in (ListStatus.ACTIVE, ListStatus.COMPLETED) and entry.start_date is None:
        entry.start_date = today
    if entry.list_status == ListStatus.COMPLETED and entry.finish_date is None:
        entry.finish_date = today

    db.session.add(entry)
    db.session.flush()

    add_history_event(entry, HistoryEventType.ADDED, details="Added to tracker")
    if any(value is not None for value in (entry.current_volume, entry.current_episode, entry.seasons_watched)):
        initial_progress_details = "Initial progress"
        if media_type == MediaType.ANIME and entry.seasons_watched is not None:
            initial_progress_details = f"Initial progress; Seasons watched: {entry.seasons_watched}"
        add_history_event(
            entry,
            HistoryEventType.PROGRESS,
            volume=entry.current_volume,
            episode=entry.current_episode,
            details=initial_progress_details,
        )

    try:
        db.session.commit()
        flash("Entry added.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to save entry.", "error")

    return redirect(url_for("main.home"))


@bp.post("/entry/<int:entry_id>/update")
def update_entry(entry_id: int):
    entry = db.get_or_404(ReadlistEntry, entry_id)
    media_type = entry.series.media_type
    old_status = entry.list_status
    old_progress = (entry.current_volume, entry.current_episode, entry.seasons_watched)
    old_downloads = entry.downloaded_volume_upto

    status_raw = (request.form.get("list_status") or old_status.value).upper()
    if status_raw in ListStatus.__members__:
        entry.list_status = ListStatus[status_raw]

    current_volume = parse_int(request.form.get("current_volume"))
    current_episode = parse_int(request.form.get("current_episode"))
    seasons_watched = parse_int(request.form.get("seasons_watched"))
    downloaded_volume_upto = parse_int(request.form.get("downloaded_volume_upto"))
    prefer_download = request.form.get("prefer_download") == "on"

    invalid_message = (
        validate_media_specific_values(media_type, current_volume, current_episode, "Current volume", "Current episode")
        or validate_anime_only_value(media_type, seasons_watched, "Seasons watched")
        or validate_download_options(media_type, prefer_download, downloaded_volume_upto)
    )
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("main.index"))

    if media_type == MediaType.BOOK:
        entry.current_volume = current_volume
        entry.downloaded_volume_upto = downloaded_volume_upto
        entry.current_episode = None
        entry.seasons_watched = None
        entry.prefer_download = prefer_download
    elif media_type == MediaType.ANIME:
        entry.current_episode = current_episode
        entry.seasons_watched = seasons_watched
        entry.current_volume = None
        entry.downloaded_volume_upto = None
        entry.prefer_download = False
    else:  # MOVIE
        entry.current_volume = None
        entry.current_episode = None
        entry.seasons_watched = None
        entry.downloaded_volume_upto = None
        entry.prefer_download = False

    entry.notes = (request.form.get("notes") or "").strip() or None
    entry.last_activity_at = datetime.utcnow()

    if entry.list_status in (ListStatus.ACTIVE, ListStatus.COMPLETED) and entry.start_date is None:
        entry.start_date = date.today()
    if entry.list_status == ListStatus.COMPLETED and entry.finish_date is None:
        entry.finish_date = date.today()
    if old_status == ListStatus.COMPLETED and entry.list_status != ListStatus.COMPLETED:
        entry.finish_date = None

    new_progress = (entry.current_volume, entry.current_episode, entry.seasons_watched)
    new_downloads = entry.downloaded_volume_upto
    status_changed = old_status != entry.list_status
    progress_changed = old_progress != new_progress
    downloads_changed = old_downloads != new_downloads
    note = (request.form.get("update_note") or "").strip()

    if status_changed:
        add_history_event(
            entry,
            HistoryEventType.STATUS_CHANGE,
            old_status=old_status,
            new_status=entry.list_status,
            details=note or None,
        )
    if progress_changed:
        progress_details = note or "Progress updated"
        if media_type == MediaType.ANIME and old_progress[2] != entry.seasons_watched:
            previous_seasons = old_progress[2] if old_progress[2] is not None else "-"
            current_seasons = entry.seasons_watched if entry.seasons_watched is not None else "-"
            progress_details = f"{progress_details}; Seasons watched: {previous_seasons} -> {current_seasons}"
        add_history_event(
            entry,
            HistoryEventType.PROGRESS,
            volume=entry.current_volume,
            episode=entry.current_episode,
            details=progress_details,
        )
    if downloads_changed:
        add_history_event(
            entry,
            HistoryEventType.DOWNLOAD_UPDATE,
            volume=entry.downloaded_volume_upto,
            details="Downloaded-up-to markers changed",
        )
    if note and not (status_changed or progress_changed):
        add_history_event(entry, HistoryEventType.NOTE, details=note)

    try:
        db.session.commit()
        flash("Entry updated.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to update entry.", "error")

    return redirect(url_for("main.index"))


@bp.post("/entry/<int:entry_id>/availability")
def update_availability(entry_id: int):
    entry = db.get_or_404(ReadlistEntry, entry_id)
    series = entry.series

    old_latest_volume = series.latest_volume
    old_latest_episode = series.latest_episode
    old_seasons_aired = series.seasons_aired
    old_publication_status = series.publication_status

    pub_raw = (request.form.get("publication_status") or old_publication_status.value).upper()
    if pub_raw in PublicationStatus.__members__:
        series.publication_status = PublicationStatus[pub_raw]

    latest_volume = parse_int(request.form.get("latest_volume"))
    latest_episode = parse_int(request.form.get("latest_episode"))
    seasons_aired = parse_int(request.form.get("seasons_aired"))
    invalid_message = validate_media_specific_values(
        series.media_type,
        latest_volume,
        latest_episode,
        "Latest volume",
        "Latest episode",
    )
    if invalid_message is None:
        invalid_message = validate_anime_only_value(series.media_type, seasons_aired, "Seasons aired")
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("main.index"))

    if series.media_type == MediaType.BOOK and latest_volume is not None:
        series.latest_volume = latest_volume
    if series.media_type == MediaType.ANIME and latest_episode is not None:
        series.latest_episode = latest_episode
    if series.media_type == MediaType.ANIME and seasons_aired is not None:
        series.seasons_aired = seasons_aired

    latest_changed = (
        (series.latest_volume != old_latest_volume)
        or (series.latest_episode != old_latest_episode)
        or (series.seasons_aired != old_seasons_aired)
    )
    publication_changed = series.publication_status != old_publication_status
    note = (request.form.get("availability_note") or "").strip()

    if not latest_changed and not publication_changed and not note:
        flash("No availability changes detected.", "error")
        return redirect(url_for("main.index"))

    details: list[str] = []
    if series.media_type == MediaType.BOOK and series.latest_volume != old_latest_volume:
        previous_volume = old_latest_volume if old_latest_volume is not None else "-"
        current_volume = series.latest_volume if series.latest_volume is not None else "-"
        details.append(f"Latest volume: {previous_volume} -> {current_volume}")
    if series.media_type == MediaType.ANIME and series.latest_episode != old_latest_episode:
        previous_episode = old_latest_episode if old_latest_episode is not None else "-"
        current_episode = series.latest_episode if series.latest_episode is not None else "-"
        details.append(f"Latest episode: {previous_episode} -> {current_episode}")
    if series.media_type == MediaType.ANIME and series.seasons_aired != old_seasons_aired:
        previous_seasons = old_seasons_aired if old_seasons_aired is not None else "-"
        current_seasons = series.seasons_aired if series.seasons_aired is not None else "-"
        details.append(f"Seasons aired: {previous_seasons} -> {current_seasons}")
    if publication_changed:
        details.append(f"Publication: {old_publication_status.value} -> {series.publication_status.value}")
    if note:
        details.append(note)

    add_history_event(
        entry,
        HistoryEventType.AVAILABILITY_UPDATE,
        volume=series.latest_volume if series.media_type == MediaType.BOOK else None,
        episode=series.latest_episode if series.media_type == MediaType.ANIME else None,
        details="; ".join(details) if details else "Availability reviewed",
    )
    entry.last_activity_at = datetime.utcnow()

    try:
        db.session.commit()
        flash("Availability updated.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to update availability.", "error")

    return redirect(url_for("main.index"))


@bp.post("/entry/<int:entry_id>/downloads")
def add_download_asset(entry_id: int):
    entry = db.get_or_404(ReadlistEntry, entry_id)
    if entry.series.media_type != MediaType.BOOK:
        flash("Download logging is available only for books.", "error")
        return redirect(url_for("main.index"))

    unit_raw = (request.form.get("unit_type") or "").upper()
    if unit_raw not in UnitType.__members__:
        flash("Invalid unit type.", "error")
        return redirect(url_for("main.index"))
    unit_type = UnitType[unit_raw]
    if unit_type != UnitType.VOLUME:
        flash("Books can only log VOLUME downloads.", "error")
        return redirect(url_for("main.index"))

    unit_number = parse_decimal(request.form.get("unit_number"))
    local_path = (request.form.get("local_path") or "").strip()
    if unit_number is None or not local_path:
        flash("Unit number and local file path are required for download history.", "error")
        return redirect(url_for("main.index"))

    asset = DownloadedAsset(
        entry=entry,
        unit_type=unit_type,
        unit_number=unit_number,
        local_path=local_path,
    )
    db.session.add(asset)
    entry.last_activity_at = datetime.utcnow()
    add_history_event(
        entry,
        HistoryEventType.NOTE,
        details=f"Downloaded {unit_raw} {unit_number} ({local_path})",
    )

    try:
        db.session.commit()
        flash("Download recorded.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to save download history.", "error")

    return redirect(url_for("main.index"))
