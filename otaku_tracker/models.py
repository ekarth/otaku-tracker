import enum
from datetime import datetime

from sqlalchemy.orm import validates

from .extensions import db


class MediaType(enum.Enum):
    BOOK = "BOOK"
    ANIME = "ANIME"
    MOVIE = "MOVIE"


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


def _normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.upper()


class Series(db.Model):
    __tablename__ = "series"
    __table_args__ = (db.UniqueConstraint("japanese_title", "english_title", "media_type", "book_type", name="uq_series_identity"),)

    id = db.Column(db.Integer, primary_key=True)
    japanese_title = db.Column(db.String(255), nullable=True)
    english_title = db.Column(db.String(255), nullable=True)
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
    seasons_aired = db.Column(db.Integer, nullable=True)
    parent_anime_id = db.Column(db.Integer, db.ForeignKey("series.id", ondelete="SET NULL"), nullable=True, default=None)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    entry = db.relationship("ReadlistEntry", back_populates="series", uselist=False, cascade="all, delete-orphan")
    parent_anime = db.relationship("Series", foreign_keys=[parent_anime_id], remote_side="Series.id", backref=db.backref("linked_movies", lazy="dynamic"))

    @validates("japanese_title", "english_title")
    def normalize_title_values(self, _key: str, value: str | None) -> str | None:
        return _normalize_title(value)

    @property
    def display_title(self) -> str:
        if self.english_title and self.japanese_title:
            return f"{self.english_title} ({self.japanese_title})"
        if self.english_title:
            return self.english_title
        if self.japanese_title:
            return self.japanese_title
        return "Untitled"


class ReadlistEntry(db.Model):
    __tablename__ = "readlist_entries"

    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey("series.id", ondelete="CASCADE"), nullable=False, unique=True)
    list_status = db.Column(db.Enum(ListStatus, native_enum=False, length=16), nullable=False, default=ListStatus.PLANNED)
    prefer_download = db.Column(db.Boolean, nullable=False, default=True)
    current_volume = db.Column(db.Integer, nullable=True)
    current_episode = db.Column(db.Integer, nullable=True)
    seasons_watched = db.Column(db.Integer, nullable=True)
    downloaded_volume_upto = db.Column(db.Integer, nullable=True)
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
