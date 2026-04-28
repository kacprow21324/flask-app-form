-- ═══════════════════════════════════════════════════════════════
--  SYSTEM EMS – Serwis obiegu dokumentacji praktyk zawodowych
--  Schemat bazy danych SQLite
--  Autor: Kacper Woszczyło (21324)
-- ═══════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA encoding = 'UTF-8';

-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 1: UŻYTKOWNICY I AUTORYZACJA
-- ═══════════════════════════════════════════════════════════════

-- Konta wszystkich użytkowników (student, UOPZ, ZOPZ, dziekanat, admin)
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,                   -- login
    password_hash   TEXT NOT NULL,                          -- bcrypt
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('student','uopz','zopz','dziekanat','admin')),
    album_number    TEXT UNIQUE,                            -- nr indeksu (tylko student)
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    email_verified  INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0,1)),
    last_login_at   DATETIME,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    DATETIME,                               -- blokada po 5 nieudanych próbach
    avatar_url      TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_album ON users(album_number);


-- Rozszerzony profil użytkownika (dane specyficzne dla roli)
CREATE TABLE user_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE,
    phone           TEXT,
    academic_year   TEXT,                                   -- np. "2024/2025"
    semester        INTEGER,                                -- dla studenta
    specialization  TEXT,
    department      TEXT,                                   -- dla pracowników
    position        TEXT,                                   -- stanowisko ZOPZ/UOPZ
    company_name    TEXT,                                   -- dla ZOPZ
    education       TEXT,                                   -- wykształcenie ZOPZ
    preferences     TEXT,                                   -- JSON: ustawienia UI
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- Aktywne sesje użytkowników
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    token           TEXT NOT NULL UNIQUE,                   -- JWT lub session token
    ip_address      TEXT,
    user_agent      TEXT,
    expires_at      DATETIME NOT NULL,
    is_revoked      INTEGER NOT NULL DEFAULT 0 CHECK (is_revoked IN (0,1)),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);


-- Historia prób logowania (NF-04)
CREATE TABLE login_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL,                          -- nie FK, bo może być nieistniejące konto
    ip_address      TEXT,
    success         INTEGER NOT NULL CHECK (success IN (0,1)),
    failure_reason  TEXT,                                   -- 'wrong_password' / 'locked' / 'unknown_user'
    attempted_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_login_email ON login_attempts(email);
CREATE INDEX idx_login_time ON login_attempts(attempted_at);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 2: ORGANIZACJA
-- ═══════════════════════════════════════════════════════════════

-- Rejestr zakładów pracy
CREATE TABLE companies (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT NOT NULL,
    nip                   TEXT UNIQUE,
    regon                 TEXT,
    address_street        TEXT,
    address_city          TEXT,
    address_zip           TEXT,
    representative_name   TEXT,
    representative_position TEXT,
    phone                 TEXT,
    email                 TEXT,
    is_verified           INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0,1)),
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_nip ON companies(nip);
CREATE INDEX idx_companies_name ON companies(name);


-- Lata akademickie
CREATE TABLE academic_years (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    year_code             TEXT NOT NULL UNIQUE,             -- "2024/2025"
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    practice_start_date   DATE NOT NULL,
    practice_end_date     DATE NOT NULL,
    is_current            INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    is_archived           INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0,1))
);

CREATE UNIQUE INDEX idx_academic_current ON academic_years(is_current) WHERE is_current = 1;


-- Słownik 13 efektów uczenia się
CREATE TABLE learning_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,                   -- '01'..'13'
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT CHECK (category IN ('wiedza','umiejetnosci','kompetencje')),
    display_order   INTEGER NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 3: PRAKTYKI
-- ═══════════════════════════════════════════════════════════════

-- Główna encja - praktyka zawodowa studenta
CREATE TABLE internships (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            INTEGER NOT NULL,
    uopz_id               INTEGER NOT NULL,                 -- opiekun uczelniany
    zopz_id               INTEGER NOT NULL,                 -- opiekun zakładowy
    company_id            INTEGER NOT NULL,
    academic_year_id      INTEGER NOT NULL,
    agreement_number      TEXT,                             -- nr porozumienia Zał.1
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    actual_end_date       DATE,                             -- jeśli przedłużona
    status                TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','active','awaiting_review','completed','archived','rejected')),
    total_hours           INTEGER NOT NULL DEFAULT 0,       -- max 960
    total_days            INTEGER NOT NULL DEFAULT 0,       -- max 120
    hours_completed       INTEGER NOT NULL DEFAULT 0,
    days_completed        INTEGER NOT NULL DEFAULT 0,
    grade_z               REAL CHECK (grade_z BETWEEN 2 AND 5),
    grade_u               REAL CHECK (grade_u BETWEEN 2 AND 5),
    grade_s               REAL CHECK (grade_s BETWEEN 2 AND 5),
    grade_e               REAL CHECK (grade_e BETWEEN 2 AND 5),
    grade_k               REAL CHECK (grade_k BETWEEN 2 AND 5),  -- K = 0.4E + 0.1S + 0.2U + 0.3Z
    specialization        TEXT,
    zopz_opinion          TEXT,
    uopz_opinion          TEXT,
    is_archived           INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0,1)),
    submitted_for_review_at DATETIME,
    completed_at          DATETIME,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)       REFERENCES users(id)           ON DELETE RESTRICT,
    FOREIGN KEY (uopz_id)          REFERENCES users(id)           ON DELETE RESTRICT,
    FOREIGN KEY (zopz_id)          REFERENCES users(id)           ON DELETE RESTRICT,
    FOREIGN KEY (company_id)       REFERENCES companies(id)       ON DELETE RESTRICT,
    FOREIGN KEY (academic_year_id) REFERENCES academic_years(id)  ON DELETE RESTRICT,

    CHECK (total_hours <= 960),
    CHECK (total_days <= 120),
    CHECK (end_date >= start_date)
);

CREATE INDEX idx_internships_student ON internships(student_id);
CREATE INDEX idx_internships_uopz ON internships(uopz_id);
CREATE INDEX idx_internships_zopz ON internships(zopz_id);
CREATE INDEX idx_internships_company ON internships(company_id);
CREATE INDEX idx_internships_year ON internships(academic_year_id);
CREATE INDEX idx_internships_status ON internships(status);


-- Wpisy dziennika praktyk (Zał.6)
CREATE TABLE diary_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id   INTEGER NOT NULL,
    day_number      INTEGER NOT NULL,                       -- 1..120
    entry_date      DATE NOT NULL,
    hours_worked    INTEGER NOT NULL,                       -- 1..8
    description     TEXT NOT NULL,                          -- min. 50 znaków
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','submitted','approved','rejected')),
    reviewed_by     INTEGER,                                -- ZOPZ który zweryfikował
    submitted_at    DATETIME,
    reviewed_at     DATETIME,
    rejection_reason TEXT,                                  -- wymagane gdy status='rejected'
    is_editable     INTEGER NOT NULL DEFAULT 1 CHECK (is_editable IN (0,1)),
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by)   REFERENCES users(id)       ON DELETE SET NULL,

    CHECK (day_number BETWEEN 1 AND 120),
    CHECK (hours_worked BETWEEN 1 AND 8),
    CHECK (LENGTH(description) >= 50),
    CHECK (status != 'rejected' OR rejection_reason IS NOT NULL),

    UNIQUE(internship_id, day_number)
);

CREATE INDEX idx_diary_internship ON diary_entries(internship_id);
CREATE INDEX idx_diary_status ON diary_entries(status);
CREATE INDEX idx_diary_date ON diary_entries(entry_date);


-- Tabela łącząca wpisy z efektami uczenia się (many-to-many)
CREATE TABLE diary_entry_outcomes (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    diary_entry_id        INTEGER NOT NULL,
    learning_outcome_id   INTEGER NOT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (diary_entry_id)      REFERENCES diary_entries(id)      ON DELETE CASCADE,
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id)  ON DELETE RESTRICT,

    UNIQUE(diary_entry_id, learning_outcome_id)
);

CREATE INDEX idx_entry_outcomes_entry ON diary_entry_outcomes(diary_entry_id);
CREATE INDEX idx_entry_outcomes_outcome ON diary_entry_outcomes(learning_outcome_id);


-- Potwierdzenia efektów uczenia się (Zał.4)
CREATE TABLE outcome_confirmations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id         INTEGER NOT NULL,
    learning_outcome_id   INTEGER NOT NULL,
    status                TEXT NOT NULL
                          CHECK (status IN ('achieved','not_achieved','partial')),
    confirmed_by          INTEGER NOT NULL,                 -- ZOPZ
    comment               TEXT,
    confirmed_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (internship_id)       REFERENCES internships(id)        ON DELETE CASCADE,
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id)  ON DELETE RESTRICT,
    FOREIGN KEY (confirmed_by)        REFERENCES users(id)              ON DELETE RESTRICT,

    UNIQUE(internship_id, learning_outcome_id)
);

CREATE INDEX idx_confirmations_internship ON outcome_confirmations(internship_id);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 4: DOKUMENTY KOŃCOWE
-- ═══════════════════════════════════════════════════════════════

-- Sprawozdanie z praktyki (Zał.7)
CREATE TABLE reports (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id             INTEGER NOT NULL UNIQUE,
    section_characteristics   TEXT,                         -- Sekcja I
    section_activities        TEXT,                         -- Sekcja II
    section_self_assessment   TEXT,                         -- Sekcja III
    status                    TEXT NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft','submitted','returned','approved')),
    submitted_at              DATETIME,
    approved_at               DATETIME,
    approved_by               INTEGER,                      -- UOPZ
    version                   INTEGER NOT NULL DEFAULT 1,
    autosaved_at              DATETIME,
    created_at                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by)   REFERENCES users(id)       ON DELETE SET NULL
);


-- Ankieta oceniająca praktykę (Zał.5) - 14 pytań Likerta
CREATE TABLE surveys (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id         INTEGER NOT NULL UNIQUE,
    answers               TEXT NOT NULL,                    -- JSON: [{q_id:1, value:5}, ...]
    additional_comments   TEXT,
    metadata              TEXT,                             -- JSON: rok ak., kierunek itp.
    submitted_at          DATETIME,
    is_anonymized         INTEGER NOT NULL DEFAULT 0 CHECK (is_anonymized IN (0,1)),
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE
);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 5: WORKFLOW I KOMENTARZE
-- ═══════════════════════════════════════════════════════════════

-- Uwagi opiekunów do sekcji dokumentów (FR-11, FR-12)
CREATE TABLE document_comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_type       TEXT NOT NULL
                        CHECK (document_type IN ('diary_entry','report','outcomes','survey')),
    document_id         INTEGER NOT NULL,                   -- polimorficzne
    section_reference   TEXT,                               -- np. 'section_I' lub 'entry_47'
    author_id           INTEGER NOT NULL,
    content             TEXT NOT NULL,
    is_resolved         INTEGER NOT NULL DEFAULT 0 CHECK (is_resolved IN (0,1)),
    parent_comment_id   INTEGER,                            -- dla wątków
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (author_id)         REFERENCES users(id)              ON DELETE RESTRICT,
    FOREIGN KEY (parent_comment_id) REFERENCES document_comments(id)  ON DELETE CASCADE
);

CREATE INDEX idx_comments_document ON document_comments(document_type, document_id);
CREATE INDEX idx_comments_author ON document_comments(author_id);
CREATE INDEX idx_comments_parent ON document_comments(parent_comment_id);


-- Historia przejść statusów (audyt workflow)
CREATE TABLE status_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL
                    CHECK (entity_type IN ('internship','diary_entry','report')),
    entity_id       INTEGER NOT NULL,
    from_status     TEXT,
    to_status       TEXT NOT NULL,
    triggered_by    INTEGER NOT NULL,
    reason          TEXT,
    transitioned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (triggered_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_transitions_entity ON status_transitions(entity_type, entity_id);
CREATE INDEX idx_transitions_user ON status_transitions(triggered_by);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 6: PDF I ZAŁĄCZNIKI
-- ═══════════════════════════════════════════════════════════════

-- Wygenerowane dokumenty PDF
CREATE TABLE generated_documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id     INTEGER NOT NULL,
    document_type     TEXT NOT NULL
                      CHECK (document_type IN ('diary','card','outcomes','report','survey','dossier')),
    template_version  TEXT,                                 -- np. "Zał.6 v2024"
    file_path         TEXT NOT NULL,
    file_name         TEXT NOT NULL,
    file_size_bytes   INTEGER NOT NULL,
    mime_type         TEXT NOT NULL DEFAULT 'application/pdf',
    checksum_sha256   TEXT,
    generated_by      INTEGER NOT NULL,
    generated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        DATETIME,                             -- dla tymczasowych linków
    download_count    INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by)  REFERENCES users(id)       ON DELETE RESTRICT
);

CREATE INDEX idx_docs_internship ON generated_documents(internship_id);
CREATE INDEX idx_docs_type ON generated_documents(document_type);


-- Historia pobrań PDF (FR-25)
CREATE TABLE document_downloads (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_document_id INTEGER NOT NULL,
    downloaded_by         INTEGER NOT NULL,
    ip_address            TEXT,
    downloaded_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (generated_document_id) REFERENCES generated_documents(id) ON DELETE CASCADE,
    FOREIGN KEY (downloaded_by)         REFERENCES users(id)               ON DELETE RESTRICT
);

CREATE INDEX idx_downloads_doc ON document_downloads(generated_document_id);
CREATE INDEX idx_downloads_user ON document_downloads(downloaded_by);


-- Załączniki do wpisów dziennika lub sprawozdania
CREATE TABLE attachments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type       TEXT NOT NULL
                      CHECK (entity_type IN ('diary_entry','report')),
    entity_id         INTEGER NOT NULL,
    file_name         TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    file_size_bytes   INTEGER NOT NULL,
    mime_type         TEXT NOT NULL,
    uploaded_by       INTEGER NOT NULL,
    uploaded_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_attachments_entity ON attachments(entity_type, entity_id);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 7: POWIADOMIENIA
-- ═══════════════════════════════════════════════════════════════

-- Powiadomienia w aplikacji (FR-21)
CREATE TABLE notifications (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id          INTEGER NOT NULL,
    type                  TEXT NOT NULL
                          CHECK (type IN ('entry_rejected','entry_approved','document_submitted',
                                          'deadline_near','grade_published','comment_added','system')),
    title                 TEXT NOT NULL,
    message               TEXT NOT NULL,
    link                  TEXT,                             -- URL do akcji
    related_entity_id     INTEGER,
    related_entity_type   TEXT,
    is_read               INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0,1)),
    read_at               DATETIME,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notif_recipient ON notifications(recipient_id);
CREATE INDEX idx_notif_unread ON notifications(recipient_id, is_read);


-- Preferencje powiadomień użytkownika
CREATE TABLE notification_preferences (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                       INTEGER NOT NULL UNIQUE,
    email_on_entry_rejected       INTEGER NOT NULL DEFAULT 1 CHECK (email_on_entry_rejected IN (0,1)),
    email_on_document_submitted   INTEGER NOT NULL DEFAULT 1 CHECK (email_on_document_submitted IN (0,1)),
    email_on_deadline             INTEGER NOT NULL DEFAULT 1 CHECK (email_on_deadline IN (0,1)),
    in_app_notifications          INTEGER NOT NULL DEFAULT 1 CHECK (in_app_notifications IN (0,1)),
    custom_settings               TEXT,                     -- JSON
    updated_at                    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ═══════════════════════════════════════════════════════════════
--  WARSTWA 8: AUDYT I KONFIGURACJA
-- ═══════════════════════════════════════════════════════════════

-- Pełen ślad audytowy (FR-25, NF-06)
CREATE TABLE audit_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER,                              -- może być NULL dla akcji systemowych
    user_role         TEXT,                                 -- zapisane dla historycznej poprawności
    action            TEXT NOT NULL
                      CHECK (action IN ('create','update','delete','submit','approve','reject',
                                        'download','login','logout','export')),
    entity_type       TEXT NOT NULL,
    entity_id         INTEGER,
    changes_before    TEXT,                                 -- JSON
    changes_after     TEXT,                                 -- JSON
    ip_address        TEXT,
    user_agent        TEXT,
    performed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_time ON audit_logs(performed_at);


-- Zdarzenia systemowe (NF-34)
CREATE TABLE system_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,                          -- 'pdf_generated' / 'backup_completed' / 'error'
    severity        TEXT NOT NULL
                    CHECK (severity IN ('info','warning','error','critical')),
    message         TEXT NOT NULL,
    context         TEXT,                                   -- JSON
    occurred_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_severity ON system_events(severity);
CREATE INDEX idx_events_time ON system_events(occurred_at);


-- Konfiguracja runtime (np. max_hours_per_day)
CREATE TABLE system_settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT NOT NULL UNIQUE,
    value           TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('int','string','bool','json')),
    description     TEXT,
    updated_by      INTEGER,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);


-- Szablony wiadomości e-mail
CREATE TABLE email_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,                   -- np. 'entry_rejected'
    subject         TEXT NOT NULL,
    body_html       TEXT NOT NULL,
    body_text       TEXT,
    variables       TEXT,                                   -- JSON: lista placeholderów
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ═══════════════════════════════════════════════════════════════
--  TRIGGERY - automatyczne aktualizacje updated_at
-- ═══════════════════════════════════════════════════════════════

CREATE TRIGGER trg_users_updated
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;

CREATE TRIGGER trg_internships_updated
    AFTER UPDATE ON internships
    FOR EACH ROW
    BEGIN
        UPDATE internships SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;

CREATE TRIGGER trg_diary_updated
    AFTER UPDATE ON diary_entries
    FOR EACH ROW
    BEGIN
        UPDATE diary_entries SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;

CREATE TRIGGER trg_reports_updated
    AFTER UPDATE ON reports
    FOR EACH ROW
    BEGIN
        UPDATE reports SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;


-- Automatyczna aktualizacja liczników w internships po zmianie wpisu dziennika
CREATE TRIGGER trg_diary_update_counters_insert
    AFTER INSERT ON diary_entries
    FOR EACH ROW
    BEGIN
        UPDATE internships
        SET hours_completed = (SELECT COALESCE(SUM(hours_worked), 0)
                               FROM diary_entries
                               WHERE internship_id = NEW.internship_id
                                 AND status IN ('submitted','approved')),
            days_completed = (SELECT COUNT(*)
                              FROM diary_entries
                              WHERE internship_id = NEW.internship_id
                                AND status IN ('submitted','approved'))
        WHERE id = NEW.internship_id;
    END;


-- Aktualizacja liczników po zmianie statusu wpisu (submit/approve/reject)
CREATE TRIGGER trg_diary_update_counters_status
    AFTER UPDATE OF status ON diary_entries
    FOR EACH ROW
    BEGIN
        UPDATE internships
        SET hours_completed = (SELECT COALESCE(SUM(hours_worked), 0)
                               FROM diary_entries
                               WHERE internship_id = NEW.internship_id
                                 AND status IN ('submitted','approved')),
            days_completed = (SELECT COUNT(*)
                              FROM diary_entries
                              WHERE internship_id = NEW.internship_id
                                AND status IN ('submitted','approved'))
        WHERE id = NEW.internship_id;
    END;


-- Walidacja: nie można przekroczyć 960 godzin łącznie
CREATE TRIGGER trg_diary_hours_limit
    BEFORE INSERT ON diary_entries
    FOR EACH ROW
    WHEN (SELECT COALESCE(SUM(hours_worked), 0)
          FROM diary_entries
          WHERE internship_id = NEW.internship_id) + NEW.hours_worked > 960
    BEGIN
        SELECT RAISE(ABORT, 'Łączna liczba godzin nie może przekroczyć 960');
    END;


-- Automatyczna blokada edycji po wysłaniu wpisu
CREATE TRIGGER trg_diary_lock_on_submit
    AFTER UPDATE OF status ON diary_entries
    FOR EACH ROW
    WHEN NEW.status = 'submitted' AND OLD.status = 'draft'
    BEGIN
        UPDATE diary_entries
        SET is_editable = 0, submitted_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;


-- Odblokowanie edycji po odrzuceniu
CREATE TRIGGER trg_diary_unlock_on_reject
    AFTER UPDATE OF status ON diary_entries
    FOR EACH ROW
    WHEN NEW.status = 'rejected'
    BEGIN
        UPDATE diary_entries
        SET is_editable = 1, version = OLD.version + 1, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;


-- ═══════════════════════════════════════════════════════════════
--  WIDOKI pomocnicze
-- ═══════════════════════════════════════════════════════════════

-- Podsumowanie postępu praktyki studenta
CREATE VIEW v_internship_progress AS
SELECT
    i.id AS internship_id,
    u.first_name || ' ' || u.last_name AS student_name,
    u.album_number,
    c.name AS company_name,
    ay.year_code AS academic_year,
    i.status,
    i.days_completed,
    i.hours_completed,
    ROUND(100.0 * i.days_completed / 120, 1) AS days_percent,
    ROUND(100.0 * i.hours_completed / 960, 1) AS hours_percent,
    (SELECT COUNT(*) FROM diary_entries WHERE internship_id = i.id AND status = 'approved') AS approved_entries,
    (SELECT COUNT(*) FROM diary_entries WHERE internship_id = i.id AND status = 'rejected') AS rejected_entries,
    (SELECT COUNT(*) FROM outcome_confirmations WHERE internship_id = i.id AND status = 'achieved') AS outcomes_achieved,
    i.grade_k AS final_grade
FROM internships i
JOIN users u ON u.id = i.student_id
JOIN companies c ON c.id = i.company_id
JOIN academic_years ay ON ay.id = i.academic_year_id;


-- Widok dla dziekanatu - przegląd wszystkich praktyk
CREATE VIEW v_dziekanat_overview AS
SELECT
    i.id,
    u.album_number,
    u.first_name || ' ' || u.last_name AS student,
    c.name AS company,
    uo.first_name || ' ' || uo.last_name AS uopz,
    zo.first_name || ' ' || zo.last_name AS zopz,
    i.status,
    i.start_date,
    i.end_date,
    i.days_completed || '/120' AS dni,
    i.hours_completed || '/960' AS godziny,
    i.grade_k AS ocena_koncowa,
    CASE
        WHEN DATE('now') > i.end_date AND i.status != 'completed' THEN 'OPÓŹNIENIE'
        WHEN DATE('now') > DATE(i.end_date, '-7 days') AND i.status = 'active' THEN 'BLISKO KOŃCA'
        ELSE 'OK'
    END AS alert
FROM internships i
JOIN users u ON u.id = i.student_id
JOIN users uo ON uo.id = i.uopz_id
JOIN users zo ON zo.id = i.zopz_id
JOIN companies c ON c.id = i.company_id;


-- Wpisy oczekujące na weryfikację (dla panelu ZOPZ)
CREATE VIEW v_entries_awaiting_review AS
SELECT
    de.id AS entry_id,
    de.internship_id,
    u.first_name || ' ' || u.last_name AS student,
    de.day_number,
    de.entry_date,
    de.hours_worked,
    SUBSTR(de.description, 1, 100) AS description_preview,
    de.submitted_at,
    ROUND((JULIANDAY('now') - JULIANDAY(de.submitted_at)) * 24, 1) AS hours_waiting
FROM diary_entries de
JOIN internships i ON i.id = de.internship_id
JOIN users u ON u.id = i.student_id
WHERE de.status = 'submitted'
ORDER BY de.submitted_at ASC;


-- ═══════════════════════════════════════════════════════════════
--  DANE POCZĄTKOWE (seed)
-- ═══════════════════════════════════════════════════════════════

-- 13 efektów uczenia się zgodnych z regulaminem praktyk
INSERT INTO learning_outcomes (code, name, description, category, display_order) VALUES
('01', 'Realizacja zadań inżynierskich', 'Ma wiedzę na temat sposobu realizacji zadań inżynierskich dotyczących informatyki z zachowaniem standardów i norm technicznych', 'wiedza', 1),
('02', 'Technologie i narzędzia', 'Zna technologie, narzędzia, metody, techniki oraz sprzęt stosowane w informatyce', 'wiedza', 2),
('03', 'Skutki ekonomiczne i prawne', 'Zna ekonomiczne, prawne skutki własnych działań oraz ograniczenia prawa autorskiego', 'wiedza', 3),
('04', 'BHP i ergonomia', 'Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka', 'wiedza', 4),
('05', 'Pozyskiwanie informacji', 'Pozyskuje informacje odnośnie technologii z różnych źródeł w języku polskim i angielskim', 'umiejetnosci', 5),
('06', 'Podnoszenie kompetencji', 'Potrafi podnieść swoje kompetencje w oparciu o kontakty ze środowiskiem inżynierskim', 'umiejetnosci', 6),
('07', 'Dokumentacja', 'Opracowuje dokumentację dotyczącą realizacji zadań i referuje ustnie zagadnienia', 'umiejetnosci', 7),
('08', 'Identyfikacja problemu', 'Potrafi zidentyfikować problem informatyczny, opisać go i przedstawić koncepcję rozwiązania', 'umiejetnosci', 8),
('09', 'Rozwiązywanie zadań inżynierskich', 'Potrafi rozwiązać rzeczywiste zadanie inżynierskie stosując normy i standardy', 'umiejetnosci', 9),
('10', 'Praca zespołowa', 'Pracuje w zespole zajmującym się zawodowo branżą IT', 'kompetencje', 10),
('11', 'Etyka zawodowa', 'Przestrzega zasad etyki zawodowej i korzysta z pomocy doświadczonych kolegów', 'kompetencje', 11),
('12', 'Komunikacja', 'Potrafi komunikować się z osobami spoza branży, pozyskiwać i przekazywać informacje', 'kompetencje', 12),
('13', 'Aktualność wiedzy', 'Dostrzega tempo dezaktualizacji wiedzy informatycznej oraz skutki działalności informatyków', 'kompetencje', 13);


-- Domyślne ustawienia systemowe
INSERT INTO system_settings (key, value, type, description) VALUES
('max_hours_per_day', '8', 'int', 'Maksymalna liczba godzin pracy dziennie'),
('max_total_hours', '960', 'int', 'Maksymalna łączna liczba godzin praktyki'),
('max_total_days', '120', 'int', 'Maksymalna liczba dni praktyki'),
('min_description_length', '50', 'int', 'Minimalna długość opisu wpisu dziennika'),
('session_timeout_minutes', '120', 'int', 'Czas wygaśnięcia sesji w minutach'),
('max_login_attempts', '5', 'int', 'Maksymalna liczba prób logowania'),
('account_lock_minutes', '15', 'int', 'Czas blokady konta po nieudanych próbach'),
('autosave_interval_seconds', '30', 'int', 'Interwał autozapisu formularzy'),
('audit_retention_years', '2', 'int', 'Okres przechowywania logów audytowych'),
('documents_retention_years', '6', 'int', 'Okres przechowywania dokumentów PDF');


-- Domyślne szablony email
INSERT INTO email_templates (code, subject, body_html, body_text, variables) VALUES
('entry_rejected',
 'Wpis dziennika został odrzucony',
 '<p>Witaj {{student_name}},</p><p>Twój wpis z dnia {{entry_date}} został odrzucony przez opiekuna.</p><p>Powód: {{rejection_reason}}</p>',
 'Witaj {{student_name}}, wpis z dnia {{entry_date}} został odrzucony. Powód: {{rejection_reason}}',
 '["student_name","entry_date","rejection_reason"]'),
('document_submitted',
 'Nowy dokument do weryfikacji',
 '<p>Student {{student_name}} przesłał dziennik do weryfikacji.</p>',
 'Student {{student_name}} przesłał dziennik do weryfikacji.',
 '["student_name"]'),
('deadline_near',
 'Zbliża się termin złożenia dokumentów',
 '<p>Do końca terminu pozostało {{days_left}} dni.</p>',
 'Do końca terminu pozostało {{days_left}} dni.',
 '["days_left"]');


-- ═══════════════════════════════════════════════════════════════
--  KONIEC SCHEMATU
-- ═══════════════════════════════════════════════════════════════
