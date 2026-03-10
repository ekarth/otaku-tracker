-- MySQL schema for Otaku Tracker
-- Create the database separately, then run this file against it.

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS otaku_tracker
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS series (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    media_type ENUM('BOOK', 'ANIME') NOT NULL,
    book_type ENUM('MANGA', 'MANHWA', 'LIGHT_NOVEL', 'N_A') NOT NULL DEFAULT 'N_A',
    publication_status ENUM('ONGOING', 'COMPLETED', 'HIATUS', 'CANCELLED') NOT NULL DEFAULT 'ONGOING',
    latest_volume INT NULL,
    latest_episode INT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_series_identity UNIQUE (title, media_type, book_type),
    INDEX idx_series_media (media_type),
    INDEX idx_series_publication_status (publication_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS readlist_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    series_id INT NOT NULL,
    list_status ENUM('PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'DROPPED') NOT NULL DEFAULT 'PLANNED',
    prefer_download TINYINT(1) NOT NULL DEFAULT 1,
    current_volume INT NULL,
    current_episode INT NULL,
    downloaded_volume_upto INT NULL,
    downloaded_episode_upto INT NULL,
    start_date DATE NULL,
    finish_date DATE NULL,
    notes TEXT NULL,
    last_activity_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_entry_series UNIQUE (series_id),
    CONSTRAINT fk_entry_series FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE,
    INDEX idx_entry_status (list_status),
    INDEX idx_entry_last_activity (last_activity_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS history_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entry_id INT NOT NULL,
    event_type ENUM('ADDED', 'PROGRESS', 'STATUS_CHANGE', 'DOWNLOAD_UPDATE', 'NOTE') NOT NULL,
    old_status ENUM('PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'DROPPED') NULL,
    new_status ENUM('PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'DROPPED') NULL,
    volume INT NULL,
    episode INT NULL,
    details VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_history_entry FOREIGN KEY (entry_id) REFERENCES readlist_entries(id) ON DELETE CASCADE,
    INDEX idx_history_entry_created (entry_id, created_at),
    INDEX idx_history_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS downloaded_assets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entry_id INT NOT NULL,
    unit_type ENUM('VOLUME', 'EPISODE') NOT NULL,
    unit_number DECIMAL(8, 2) NOT NULL,
    local_path VARCHAR(500) NOT NULL,
    downloaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_download_entry FOREIGN KEY (entry_id) REFERENCES readlist_entries(id) ON DELETE CASCADE,
    INDEX idx_download_entry_time (entry_id, downloaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
