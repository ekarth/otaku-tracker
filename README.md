# Otaku Tracker (Flask + MySQL)

Track manga, manhwa, light novels, and anime in one place with:
- Current read/watch list
- Ongoing/completed status
- Latest volume/episode availability updates with history logs
- Download preference and downloaded-unit tracking
- Full history of progress and status changes

## 1) Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Create and initialize MySQL database

```sql
CREATE DATABASE otaku_tracker
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Then run:

```powershell
mysql -u root -p otaku_tracker < schema.sql
```

## 3) Configure environment

Copy `.env.example` to `.env` and set your MySQL credentials.
The app reads settings through a typed Pydantic settings model.

## 4) Run the app

```powershell
flask --app app.py run --debug
```

Open: `http://127.0.0.1:5000`

## Optional ORM table creation

If you prefer SQLAlchemy to create tables instead of `schema.sql`, run:

```powershell
flask --app app.py init-db
```

## Main tables

- `series`: Japanese/English title metadata for BOOK/ANIME, subtype, and release status.
- `readlist_entries`: one tracked row per series with your current progress and download preference.
  For anime, this includes seasons aired/watched tracking.
- `history_events`: immutable log for add/progress/status/download-note changes.
- `downloaded_assets`: detailed local download history (unit + path).
