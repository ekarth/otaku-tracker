"""Integration tests for Flask routes."""
import pytest

from otaku_tracker.extensions import db
from otaku_tracker.models import BookType, ListStatus, MediaType, PublicationStatus, ReadlistEntry, Series


def _make_series(app, media_type=MediaType.ANIME, english_title="TEST ANIME", book_type=BookType.N_A, **kwargs):
    """Helper to insert a Series + ReadlistEntry directly."""
    with app.app_context():
        s = Series(
            english_title=english_title,
            media_type=media_type,
            book_type=book_type,
            publication_status=PublicationStatus.ONGOING,
            **kwargs,
        )
        db.session.add(s)
        db.session.flush()
        e = ReadlistEntry(series=s, list_status=ListStatus.PLANNED)
        db.session.add(e)
        db.session.commit()
        return s.id, e.id


class TestHomeRoute:
    def test_get_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_contains_add_form(self, client):
        resp = client.get("/")
        assert b"Add To Tracker" in resp.data


class TestReadlistRoute:
    def test_get_empty_returns_200(self, client):
        resp = client.get("/readlist")
        assert resp.status_code == 200

    def test_media_filter_applied(self, client, app):
        _make_series(app, media_type=MediaType.BOOK, english_title="A MANGA", book_type=BookType.MANGA)
        resp = client.get("/readlist?media=BOOK")
        assert resp.status_code == 200
        assert b"A MANGA" in resp.data

    def test_movie_entries_visible(self, client, app):
        _make_series(app, media_type=MediaType.MOVIE, english_title="A MOVIE")
        resp = client.get("/readlist")
        assert b"A MOVIE" in resp.data

    def test_invalid_page_returns_empty(self, client):
        resp = client.get("/readlist?page=9999")
        assert resp.status_code == 200


class TestAddEntry:
    def test_add_anime_success(self, client):
        resp = client.post("/add", data={
            "english_title": "NARUTO",
            "media_type": "ANIME",
            "publication_status": "ONGOING",
            "list_status": "PLANNED",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Entry added" in resp.data

    def test_add_book_success(self, client):
        resp = client.post("/add", data={
            "english_title": "ONE PIECE",
            "media_type": "BOOK",
            "book_type": "MANGA",
            "publication_status": "ONGOING",
            "list_status": "PLANNED",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Entry added" in resp.data

    def test_add_standalone_movie(self, client):
        resp = client.post("/add", data={
            "english_title": "YOUR NAME",
            "media_type": "MOVIE",
            "publication_status": "COMPLETED",
            "list_status": "COMPLETED",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Entry added" in resp.data

    def test_add_movie_with_parent_anime(self, client, app):
        series_id, _ = _make_series(app, media_type=MediaType.ANIME, english_title="DEMON SLAYER")
        resp = client.post("/add", data={
            "english_title": "DEMON SLAYER MOVIE",
            "media_type": "MOVIE",
            "publication_status": "COMPLETED",
            "list_status": "PLANNED",
            "parent_anime_id": str(series_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Entry added" in resp.data

    def test_add_movie_with_invalid_parent_fails(self, client):
        resp = client.post("/add", data={
            "english_title": "ORPHAN MOVIE",
            "media_type": "MOVIE",
            "publication_status": "COMPLETED",
            "list_status": "PLANNED",
            "parent_anime_id": "99999",
        }, follow_redirects=True)
        assert b"does not exist" in resp.data

    def test_missing_title_fails(self, client):
        resp = client.post("/add", data={
            "media_type": "ANIME",
            "publication_status": "ONGOING",
        }, follow_redirects=True)
        assert b"at least one title" in resp.data

    def test_duplicate_entry_fails(self, client, app):
        _make_series(app, media_type=MediaType.ANIME, english_title="BLEACH")
        resp = client.post("/add", data={
            "english_title": "BLEACH",
            "media_type": "ANIME",
            "publication_status": "ONGOING",
            "list_status": "PLANNED",
        }, follow_redirects=True)
        assert b"already in your tracker" in resp.data

    def test_book_with_episode_fails(self, client):
        resp = client.post("/add", data={
            "english_title": "MANGA WITH EP",
            "media_type": "BOOK",
            "book_type": "MANGA",
            "publication_status": "ONGOING",
            "latest_episode": "5",
        }, follow_redirects=True)
        assert b"only allowed for anime" in resp.data

    def test_movie_with_volume_fails(self, client):
        resp = client.post("/add", data={
            "english_title": "MOVIE WITH VOL",
            "media_type": "MOVIE",
            "publication_status": "COMPLETED",
            "latest_volume": "1",
        }, follow_redirects=True)
        assert b"only allowed for books" in resp.data


class TestUpdateEntry:
    def test_update_status(self, client, app):
        _, entry_id = _make_series(app, media_type=MediaType.ANIME, english_title="UPDATE TEST")
        resp = client.post(f"/entry/{entry_id}/update", data={
            "list_status": "ACTIVE",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Entry updated" in resp.data

    def test_movie_update_ignores_episode_fields(self, client, app):
        _, entry_id = _make_series(app, media_type=MediaType.MOVIE, english_title="MOVIE UPDATE")
        resp = client.post(f"/entry/{entry_id}/update", data={
            "list_status": "COMPLETED",
            "current_episode": "5",  # Should be silently ignored, not cause a validation error
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_update_nonexistent_entry_returns_404(self, client):
        resp = client.post("/entry/99999/update", data={"list_status": "ACTIVE"})
        assert resp.status_code == 404


class TestUpdateAvailability:
    def test_update_book_volume(self, client, app):
        _, entry_id = _make_series(
            app, media_type=MediaType.BOOK, english_title="AVAIL BOOK", book_type=BookType.MANGA
        )
        resp = client.post(f"/entry/{entry_id}/availability", data={
            "publication_status": "ONGOING",
            "latest_volume": "10",
        }, follow_redirects=True)
        assert b"Availability updated" in resp.data

    def test_update_anime_episode(self, client, app):
        _, entry_id = _make_series(app, media_type=MediaType.ANIME, english_title="AVAIL ANIME")
        resp = client.post(f"/entry/{entry_id}/availability", data={
            "publication_status": "ONGOING",
            "latest_episode": "24",
        }, follow_redirects=True)
        assert b"Availability updated" in resp.data

    def test_update_movie_pub_status_only(self, client, app):
        _, entry_id = _make_series(app, media_type=MediaType.MOVIE, english_title="AVAIL MOVIE")
        resp = client.post(f"/entry/{entry_id}/availability", data={
            "publication_status": "COMPLETED",
        }, follow_redirects=True)
        assert b"Availability updated" in resp.data

    def test_no_changes_returns_error(self, client, app):
        _, entry_id = _make_series(app, media_type=MediaType.ANIME, english_title="NO CHANGE ANIME")
        resp = client.post(f"/entry/{entry_id}/availability", data={
            "publication_status": "ONGOING",
        }, follow_redirects=True)
        assert b"No availability changes" in resp.data


class TestHistoryRoute:
    def test_get_returns_200(self, client):
        resp = client.get("/history")
        assert resp.status_code == 200

    def test_media_filter(self, client):
        resp = client.get("/history?media=ANIME")
        assert resp.status_code == 200


class TestExportCSV:
    def test_returns_csv_content_type(self, client):
        resp = client.get("/readlist/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_csv_header_columns(self, client):
        resp = client.get("/readlist/export")
        first_line = resp.data.decode("utf-8").splitlines()[0]
        assert "parent_anime" in first_line
        assert "downloaded_volume_upto" in first_line
        assert "downloaded_episode_upto" not in first_line
