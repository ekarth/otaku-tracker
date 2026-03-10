import enum
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    flask_secret_key: str = Field(default="change-this-secret", validation_alias="FLASK_SECRET_KEY")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    mysql_host: str = Field(default="127.0.0.1", validation_alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", validation_alias="MYSQL_USER")
    mysql_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    mysql_db: str = Field(default="otaku_tracker", validation_alias="MYSQL_DB")

    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        encoded_user = quote_plus(self.mysql_user)
        encoded_password = quote_plus(self.mysql_password)
        return (
            "mysql+pymysql://"
            f"{encoded_user}:{encoded_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            "?charset=utf8mb4"
        )


settings = Settings()


app = Flask(__name__)
app.config["SECRET_KEY"] = settings.flask_secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class MediaType(enum.Enum):
    BOOK = "BOOK"
    ANIME = "ANIME"


class BookType(enum.Enum):
    MANGA = "MANGA"
    MANHWA = "MANHWA"
    LIGHT_NOVEL = "LIGHT_NOVEL"
    N_A = "N_A"


class PublicationStatus(enum.Enum):
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    HIATUS = "HIATUS"
    CANCELLED = "CANCELLED"


class ListStatus(enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"


class HistoryEventType(enum.Enum):
    ADDED = "ADDED"
    PROGRESS = "PROGRESS"
    AVAILABILITY_UPDATE = "AVAILABILITY_UPDATE"
    STATUS_CHANGE = "STATUS_CHANGE"
    DOWNLOAD_UPDATE = "DOWNLOAD_UPDATE"
    NOTE = "NOTE"


class UnitType(enum.Enum):
    VOLUME = "VOLUME"
    EPISODE = "EPISODE"


class Series(db.Model):
    __tablename__ = "series"
    __table_args__ = (db.UniqueConstraint("title", "media_type", "book_type", name="uq_series_identity"),)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.Enum(MediaType, native_enum=False, length=16), nullable=False)
    book_type = db.Column(
        db.Enum(BookType, native_enum=False, length=16),
        nullable=False,
        default=BookType.N_A,
    )
    publication_status = db.Column(
        db.Enum(PublicationStatus, native_enum=False, length=16),
        nullable=False,
        default=PublicationStatus.ONGOING,
    )
    latest_volume = db.Column(db.Integer, nullable=True)
    latest_episode = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    entry = db.relationship("ReadlistEntry", back_populates="series", uselist=False, cascade="all, delete-orphan")


class ReadlistEntry(db.Model):
    __tablename__ = "readlist_entries"

    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey("series.id", ondelete="CASCADE"), nullable=False, unique=True)
    list_status = db.Column(db.Enum(ListStatus, native_enum=False, length=16), nullable=False, default=ListStatus.PLANNED)
    prefer_download = db.Column(db.Boolean, nullable=False, default=True)
    current_volume = db.Column(db.Integer, nullable=True)
    current_episode = db.Column(db.Integer, nullable=True)
    downloaded_volume_upto = db.Column(db.Integer, nullable=True)
    downloaded_episode_upto = db.Column(db.Integer, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    finish_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    series = db.relationship("Series", back_populates="entry")
    history_events = db.relationship(
        "HistoryEvent",
        back_populates="entry",
        order_by="desc(HistoryEvent.created_at)",
        cascade="all, delete-orphan",
    )
    downloaded_assets = db.relationship(
        "DownloadedAsset",
        back_populates="entry",
        order_by="desc(DownloadedAsset.downloaded_at)",
        cascade="all, delete-orphan",
    )


class HistoryEvent(db.Model):
    __tablename__ = "history_events"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("readlist_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = db.Column(db.Enum(HistoryEventType, native_enum=False, length=24), nullable=False)
    old_status = db.Column(db.Enum(ListStatus, native_enum=False, length=16), nullable=True)
    new_status = db.Column(db.Enum(ListStatus, native_enum=False, length=16), nullable=True)
    volume = db.Column(db.Integer, nullable=True)
    episode = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    entry = db.relationship("ReadlistEntry", back_populates="history_events")


class DownloadedAsset(db.Model):
    __tablename__ = "downloaded_assets"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("readlist_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_type = db.Column(db.Enum(UnitType, native_enum=False, length=16), nullable=False)
    unit_number = db.Column(db.Numeric(8, 2), nullable=False)
    local_path = db.Column(db.String(500), nullable=False)
    downloaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    entry = db.relationship("ReadlistEntry", back_populates="downloaded_assets")


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


def validate_media_specific_values(
    media_type: MediaType,
    volume_value: int | None,
    episode_value: int | None,
    volume_label: str,
    episode_label: str,
) -> str | None:
    if media_type == MediaType.BOOK and episode_value is not None:
        return f"{episode_label} is only allowed for anime."
    if media_type == MediaType.ANIME and volume_value is not None:
        return f"{volume_label} is only allowed for books."
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


def progress_text(entry: ReadlistEntry) -> str:
    if entry.series.media_type == MediaType.ANIME:
        watched = f"Ep {entry.current_episode}" if entry.current_episode is not None else "Not started"
        total = f"/ {entry.series.latest_episode}" if entry.series.latest_episode is not None else ""
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
    if not entry.prefer_download:
        return "Streaming / online"

    if entry.series.media_type == MediaType.ANIME:
        if entry.downloaded_episode_upto is None:
            return "No episodes downloaded"
        return f"Downloaded up to Ep {entry.downloaded_episode_upto}"

    parts = []
    if entry.downloaded_volume_upto is not None:
        parts.append(f"Vol {entry.downloaded_volume_upto}")
    if not parts:
        return "No volumes downloaded"
    return f"Downloaded up to {' | '.join(parts)}"


@app.template_filter("progress_text")
def progress_text_filter(entry: ReadlistEntry) -> str:
    return progress_text(entry)


@app.template_filter("downloaded_text")
def downloaded_text_filter(entry: ReadlistEntry) -> str:
    return downloaded_text(entry)


@app.template_filter("dt")
def datetime_filter(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


@app.get("/")
def index():
    media_filter = request.args.get("media", "ALL").upper()
    status_filter = request.args.get("status", "ALL").upper()

    query = ReadlistEntry.query.join(Series)
    if media_filter in MediaType.__members__:
        query = query.filter(Series.media_type == MediaType[media_filter])
    if status_filter in ListStatus.__members__:
        query = query.filter(ReadlistEntry.list_status == ListStatus[status_filter])

    entries = query.order_by(ReadlistEntry.updated_at.desc()).all()

    preview_query = HistoryEvent.query.join(ReadlistEntry).join(Series)
    if media_filter in MediaType.__members__:
        preview_query = preview_query.filter(Series.media_type == MediaType[media_filter])
    history_preview = preview_query.order_by(HistoryEvent.created_at.desc()).limit(12).all()

    return render_template(
        "index.html",
        entries=entries,
        history_preview=history_preview,
        media_filter=media_filter,
        status_filter=status_filter,
        media_values=[m.value for m in MediaType],
        status_values=[s.value for s in ListStatus],
        add_book_types=[b.value for b in BookType if b != BookType.N_A],
        publication_values=[p.value for p in PublicationStatus],
    )


@app.post("/add")
def add_entry():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("index"))

    media_raw = (request.form.get("media_type") or "").upper()
    if media_raw not in MediaType.__members__:
        flash("Invalid media type.", "error")
        return redirect(url_for("index"))
    media_type = MediaType[media_raw]

    if media_type == MediaType.BOOK:
        book_raw = (request.form.get("book_type") or "").upper()
        if book_raw not in BookType.__members__ or book_raw == BookType.N_A.value:
            flash("Choose MANGA, MANHWA, or LIGHT_NOVEL for books.", "error")
            return redirect(url_for("index"))
        book_type = BookType[book_raw]
    else:
        book_type = BookType.N_A

    pub_raw = (request.form.get("publication_status") or "ONGOING").upper()
    publication_status = PublicationStatus[pub_raw] if pub_raw in PublicationStatus.__members__ else PublicationStatus.ONGOING
    latest_volume = parse_int(request.form.get("latest_volume"))
    latest_episode = parse_int(request.form.get("latest_episode"))
    current_volume = parse_int(request.form.get("current_volume"))
    current_episode = parse_int(request.form.get("current_episode"))
    downloaded_volume_upto = parse_int(request.form.get("downloaded_volume_upto"))
    downloaded_episode_upto = parse_int(request.form.get("downloaded_episode_upto"))

    invalid_message = (
        validate_media_specific_values(media_type, latest_volume, latest_episode, "Latest volume", "Latest episode")
        or validate_media_specific_values(media_type, current_volume, current_episode, "Current volume", "Current episode")
        or validate_media_specific_values(
            media_type,
            downloaded_volume_upto,
            downloaded_episode_upto,
            "Downloaded volume",
            "Downloaded episode",
        )
    )
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("index"))

    series = Series.query.filter_by(title=title, media_type=media_type, book_type=book_type).first()
    if series is None:
        series = Series(
            title=title,
            media_type=media_type,
            book_type=book_type,
            publication_status=publication_status,
            latest_volume=latest_volume if media_type == MediaType.BOOK else None,
            latest_episode=latest_episode if media_type == MediaType.ANIME else None,
        )
        db.session.add(series)
        db.session.flush()
    else:
        series.publication_status = publication_status
        if media_type == MediaType.BOOK and latest_volume is not None:
            series.latest_volume = latest_volume
        if media_type == MediaType.ANIME and latest_episode is not None:
            series.latest_episode = latest_episode

    if ReadlistEntry.query.filter_by(series_id=series.id).first() is not None:
        flash("This title is already in your tracker.", "error")
        db.session.rollback()
        return redirect(url_for("index"))

    status_raw = (request.form.get("list_status") or "PLANNED").upper()
    list_status = ListStatus[status_raw] if status_raw in ListStatus.__members__ else ListStatus.PLANNED
    today = date.today()

    entry = ReadlistEntry(
        series=series,
        list_status=list_status,
        prefer_download=request.form.get("prefer_download") == "on",
        current_volume=current_volume if media_type == MediaType.BOOK else None,
        current_episode=current_episode if media_type == MediaType.ANIME else None,
        downloaded_volume_upto=downloaded_volume_upto if media_type == MediaType.BOOK else None,
        downloaded_episode_upto=downloaded_episode_upto if media_type == MediaType.ANIME else None,
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
    if any(value is not None for value in (entry.current_volume, entry.current_episode)):
        add_history_event(
            entry,
            HistoryEventType.PROGRESS,
            volume=entry.current_volume,
            episode=entry.current_episode,
            details="Initial progress",
        )

    try:
        db.session.commit()
        flash("Entry added.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to save entry.", "error")

    return redirect(url_for("index"))


@app.post("/entry/<int:entry_id>/update")
def update_entry(entry_id: int):
    entry = ReadlistEntry.query.get_or_404(entry_id)
    media_type = entry.series.media_type
    old_status = entry.list_status
    old_progress = (entry.current_volume, entry.current_episode)
    old_downloads = (entry.downloaded_volume_upto, entry.downloaded_episode_upto)

    status_raw = (request.form.get("list_status") or old_status.value).upper()
    if status_raw in ListStatus.__members__:
        entry.list_status = ListStatus[status_raw]

    current_volume = parse_int(request.form.get("current_volume"))
    current_episode = parse_int(request.form.get("current_episode"))
    downloaded_volume_upto = parse_int(request.form.get("downloaded_volume_upto"))
    downloaded_episode_upto = parse_int(request.form.get("downloaded_episode_upto"))

    invalid_message = (
        validate_media_specific_values(media_type, current_volume, current_episode, "Current volume", "Current episode")
        or validate_media_specific_values(
            media_type,
            downloaded_volume_upto,
            downloaded_episode_upto,
            "Downloaded volume",
            "Downloaded episode",
        )
    )
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("index"))

    if media_type == MediaType.BOOK:
        entry.current_volume = current_volume
        entry.downloaded_volume_upto = downloaded_volume_upto
        entry.current_episode = None
        entry.downloaded_episode_upto = None
    else:
        entry.current_episode = current_episode
        entry.downloaded_episode_upto = downloaded_episode_upto
        entry.current_volume = None
        entry.downloaded_volume_upto = None

    entry.prefer_download = request.form.get("prefer_download") == "on"
    entry.notes = (request.form.get("notes") or "").strip() or None
    entry.last_activity_at = datetime.utcnow()

    if entry.list_status in (ListStatus.ACTIVE, ListStatus.COMPLETED) and entry.start_date is None:
        entry.start_date = date.today()
    if entry.list_status == ListStatus.COMPLETED and entry.finish_date is None:
        entry.finish_date = date.today()
    if old_status == ListStatus.COMPLETED and entry.list_status != ListStatus.COMPLETED:
        entry.finish_date = None

    new_progress = (entry.current_volume, entry.current_episode)
    new_downloads = (entry.downloaded_volume_upto, entry.downloaded_episode_upto)
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
        add_history_event(
            entry,
            HistoryEventType.PROGRESS,
            volume=entry.current_volume,
            episode=entry.current_episode,
            details=note or "Progress updated",
        )
    if downloads_changed:
        add_history_event(
            entry,
            HistoryEventType.DOWNLOAD_UPDATE,
            volume=entry.downloaded_volume_upto,
            episode=entry.downloaded_episode_upto,
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

    return redirect(url_for("index"))


@app.post("/entry/<int:entry_id>/availability")
def update_availability(entry_id: int):
    entry = ReadlistEntry.query.get_or_404(entry_id)
    series = entry.series

    old_latest_volume = series.latest_volume
    old_latest_episode = series.latest_episode
    old_publication_status = series.publication_status

    pub_raw = (request.form.get("publication_status") or old_publication_status.value).upper()
    if pub_raw in PublicationStatus.__members__:
        series.publication_status = PublicationStatus[pub_raw]

    latest_volume = parse_int(request.form.get("latest_volume"))
    latest_episode = parse_int(request.form.get("latest_episode"))
    invalid_message = validate_media_specific_values(
        series.media_type,
        latest_volume,
        latest_episode,
        "Latest volume",
        "Latest episode",
    )
    if invalid_message:
        flash(invalid_message, "error")
        return redirect(url_for("index"))

    if series.media_type == MediaType.BOOK and latest_volume is not None:
        series.latest_volume = latest_volume
    if series.media_type == MediaType.ANIME and latest_episode is not None:
        series.latest_episode = latest_episode

    latest_changed = (series.latest_volume != old_latest_volume) or (series.latest_episode != old_latest_episode)
    publication_changed = series.publication_status != old_publication_status
    note = (request.form.get("availability_note") or "").strip()

    if not latest_changed and not publication_changed and not note:
        flash("No availability changes detected.", "error")
        return redirect(url_for("index"))

    details: list[str] = []
    if series.media_type == MediaType.BOOK and series.latest_volume != old_latest_volume:
        previous_volume = old_latest_volume if old_latest_volume is not None else "-"
        current_volume = series.latest_volume if series.latest_volume is not None else "-"
        details.append(f"Latest volume: {previous_volume} -> {current_volume}")
    if series.media_type == MediaType.ANIME and series.latest_episode != old_latest_episode:
        previous_episode = old_latest_episode if old_latest_episode is not None else "-"
        current_episode = series.latest_episode if series.latest_episode is not None else "-"
        details.append(f"Latest episode: {previous_episode} -> {current_episode}")
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

    return redirect(url_for("index"))


@app.post("/entry/<int:entry_id>/downloads")
def add_download_asset(entry_id: int):
    entry = ReadlistEntry.query.get_or_404(entry_id)

    unit_raw = (request.form.get("unit_type") or "").upper()
    if unit_raw not in UnitType.__members__:
        flash("Invalid unit type.", "error")
        return redirect(url_for("index"))
    unit_type = UnitType[unit_raw]
    if entry.series.media_type == MediaType.BOOK and unit_type != UnitType.VOLUME:
        flash("Books can only log VOLUME downloads.", "error")
        return redirect(url_for("index"))
    if entry.series.media_type == MediaType.ANIME and unit_type != UnitType.EPISODE:
        flash("Anime can only log EPISODE downloads.", "error")
        return redirect(url_for("index"))

    unit_number = parse_decimal(request.form.get("unit_number"))
    local_path = (request.form.get("local_path") or "").strip()
    if unit_number is None or not local_path:
        flash("Unit number and local file path are required for download history.", "error")
        return redirect(url_for("index"))

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

    return redirect(url_for("index"))


@app.get("/history")
def history():
    media_filter = request.args.get("media", "ALL").upper()
    query = HistoryEvent.query.join(ReadlistEntry).join(Series)
    if media_filter in MediaType.__members__:
        query = query.filter(Series.media_type == MediaType[media_filter])
    events = query.order_by(HistoryEvent.created_at.desc()).limit(500).all()
    return render_template(
        "history.html",
        events=events,
        media_filter=media_filter,
        media_values=[m.value for m in MediaType],
    )


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database tables created.")


if __name__ == "__main__":
    app.run(debug=True)
