import csv
import io
from datetime import datetime

from flask import Blueprint, Response, render_template, request

from ..extensions import db
from ..filters import downloaded_text, progress_text
from ..models import (
    BookType,
    HistoryEvent,
    ListStatus,
    MediaType,
    PublicationStatus,
    ReadlistEntry,
    Series,
)

bp = Blueprint("main", __name__)

PER_PAGE_READLIST = 25
PER_PAGE_HISTORY = 50


def _get_readlist_filters() -> tuple[str, str, str, str]:
    media_filter = request.args.get("media", "ALL").upper()
    status_filter = request.args.get("status", "ALL").upper()
    release_filter = request.args.get("release_status", "ALL").upper()
    book_type_filter = request.args.get("book_type", "ALL").upper()
    return media_filter, status_filter, release_filter, book_type_filter


def _build_readlist_query(media_filter: str, status_filter: str, release_filter: str, book_type_filter: str):
    query = ReadlistEntry.query.join(Series)
    if media_filter in MediaType.__members__:
        query = query.filter(Series.media_type == MediaType[media_filter])
    if status_filter in ListStatus.__members__:
        query = query.filter(ReadlistEntry.list_status == ListStatus[status_filter])
    if release_filter in PublicationStatus.__members__:
        query = query.filter(Series.publication_status == PublicationStatus[release_filter])
    if book_type_filter in BookType.__members__ and book_type_filter != BookType.N_A.value:
        query = query.filter(Series.book_type == BookType[book_type_filter])
    return query


@bp.get("/")
def home():
    anime_series = Series.query.filter_by(media_type=MediaType.ANIME).order_by(Series.english_title, Series.japanese_title).all()
    return render_template(
        "home.html",
        media_values=[m.value for m in MediaType],
        status_values=[s.value for s in ListStatus],
        add_book_types=[b.value for b in BookType if b != BookType.N_A],
        publication_values=[p.value for p in PublicationStatus],
        anime_series=anime_series,
    )


@bp.get("/readlist")
def index():
    media_filter, status_filter, release_filter, book_type_filter = _get_readlist_filters()
    page = request.args.get("page", 1, type=int)

    query = _build_readlist_query(media_filter, status_filter, release_filter, book_type_filter)
    pagination = query.order_by(ReadlistEntry.updated_at.desc()).paginate(
        page=page, per_page=PER_PAGE_READLIST, error_out=False
    )

    return render_template(
        "index.html",
        entries=pagination.items,
        pagination=pagination,
        media_filter=media_filter,
        status_filter=status_filter,
        release_filter=release_filter,
        book_type_filter=book_type_filter,
        media_values=[m.value for m in MediaType],
        status_values=[s.value for s in ListStatus],
        publication_values=[p.value for p in PublicationStatus],
        book_type_values=[b.value for b in BookType if b != BookType.N_A],
    )


@bp.get("/readlist/export")
def export_readlist_csv():
    media_filter, status_filter, release_filter, book_type_filter = _get_readlist_filters()
    entries = _build_readlist_query(media_filter, status_filter, release_filter, book_type_filter).order_by(
        ReadlistEntry.updated_at.desc()
    ).all()

    csv_output = io.StringIO(newline="")
    writer = csv.writer(csv_output)
    writer.writerow(
        [
            "japanese_title",
            "english_title",
            "display_title",
            "media_type",
            "book_type",
            "parent_anime",
            "release_status",
            "list_status",
            "current_volume",
            "current_episode",
            "seasons_watched",
            "latest_volume",
            "latest_episode",
            "seasons_aired",
            "prefer_download",
            "downloaded_volume_upto",
            "progress_text",
            "downloaded_text",
            "start_date",
            "finish_date",
            "last_activity_at",
            "notes",
        ]
    )

    for entry in entries:
        series = entry.series
        writer.writerow(
            [
                series.japanese_title or "",
                series.english_title or "",
                series.display_title,
                series.media_type.value,
                series.book_type.value if series.media_type == MediaType.BOOK else "",
                series.parent_anime.display_title if series.media_type == MediaType.MOVIE and series.parent_anime else "",
                series.publication_status.value,
                entry.list_status.value,
                entry.current_volume if entry.current_volume is not None else "",
                entry.current_episode if entry.current_episode is not None else "",
                entry.seasons_watched if entry.seasons_watched is not None else "",
                series.latest_volume if series.latest_volume is not None else "",
                series.latest_episode if series.latest_episode is not None else "",
                series.seasons_aired if series.seasons_aired is not None else "",
                "YES" if entry.prefer_download else "NO",
                entry.downloaded_volume_upto if entry.downloaded_volume_upto is not None else "",
                progress_text(entry),
                downloaded_text(entry),
                entry.start_date.isoformat() if entry.start_date else "",
                entry.finish_date.isoformat() if entry.finish_date else "",
                entry.last_activity_at.strftime("%Y-%m-%d %H:%M:%S") if entry.last_activity_at else "",
                entry.notes or "",
            ]
        )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = (
        f"readlist_{media_filter.lower()}_{status_filter.lower()}_{release_filter.lower()}_"
        f"{book_type_filter.lower()}_{timestamp}.csv"
    )
    response = Response(csv_output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@bp.get("/history")
def history():
    media_filter = request.args.get("media", "ALL").upper()
    page = request.args.get("page", 1, type=int)

    query = HistoryEvent.query.join(ReadlistEntry).join(Series)
    if media_filter in MediaType.__members__:
        query = query.filter(Series.media_type == MediaType[media_filter])

    pagination = query.order_by(HistoryEvent.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE_HISTORY, error_out=False
    )

    return render_template(
        "history.html",
        events=pagination.items,
        pagination=pagination,
        media_filter=media_filter,
        media_values=[m.value for m in MediaType],
    )
