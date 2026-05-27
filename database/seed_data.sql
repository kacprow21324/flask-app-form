-- ═══════════════════════════════════════════════════════════════
--  DANE TESTOWE – System EMS (ems_schema.sql)
--  Uruchom PO ems_schema.sql w DBeaver na świeżej bazie.
--  Hasła są placeholderami – w prawdziwej bazie używaj seed.py.
-- ═══════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;

-- ──────────────────────────────────────────────────────────────
--  UŻYTKOWNICY
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO users
    (email, password_hash, first_name, last_name, role, album_number, is_active, email_verified)
VALUES
    -- Studenci
    ('student@student.ans-elblag.pl', 'bcrypt_hash_placeholder', 'Aleksandra', 'Kowalska',  'student',   '21001', 1, 1),
    ('student2@student.ans-elblag.pl','bcrypt_hash_placeholder', 'Marek',      'Nowak',     'student',   '21002', 1, 1),
    ('student3@student.ans-elblag.pl','bcrypt_hash_placeholder', 'Katarzyna',  'Wróbel',    'student',   '21003', 1, 1),
    ('student4@student.ans-elblag.pl','bcrypt_hash_placeholder', 'Piotr',      'Zając',     'student',   '21004', 1, 1),
    ('student5@student.ans-elblag.pl','bcrypt_hash_placeholder', 'Natalia',    'Lewandowska','student',  '21005', 1, 1),
    -- Opiekunowie
    ('opiekun@ans-elblag.pl',          'bcrypt_hash_placeholder', 'Irena',     'Malinowska','uopz',      NULL,    1, 1),
    ('opiekun2@ans-elblag.pl',         'bcrypt_hash_placeholder', 'Tomasz',    'Witek',     'uopz',      NULL,    1, 1),
    ('zopz@firma.pl',                  'bcrypt_hash_placeholder', 'Zbigniew',  'Ostrowski', 'zopz',      NULL,    1, 1),
    -- Dziekanat i admin
    ('dziekanat@ans-elblag.pl',        'bcrypt_hash_placeholder', 'Dorota',    'Kamińska',  'dziekanat', NULL,    1, 1),
    ('admin@ans-elblag.pl',            'bcrypt_hash_placeholder', 'Adam',      'Wiśniewski','admin',     NULL,    1, 1);


-- ──────────────────────────────────────────────────────────────
--  PROFILE UŻYTKOWNIKÓW
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO user_profiles (user_id, phone, academic_year, semester, specialization, department, position)
SELECT id, '+48 512 100 001', '2025/2026', 6,
       'Administracja systemów i sieci komputerowych (ASiSK)', NULL, NULL
FROM users WHERE album_number = '21001';

INSERT OR IGNORE INTO user_profiles (user_id, phone, academic_year, semester, specialization, department, position)
SELECT id, '+48 512 100 002', '2025/2026', 6,
       'Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)', NULL, NULL
FROM users WHERE album_number = '21002';

INSERT OR IGNORE INTO user_profiles (user_id, phone, academic_year, semester, specialization, department, position)
SELECT id, '+48 512 100 003', '2025/2026', 6,
       'Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)', NULL, NULL
FROM users WHERE album_number = '21003';

INSERT OR IGNORE INTO user_profiles (user_id, phone, academic_year, semester, specialization)
SELECT id, '+48 512 100 004', '2025/2026', 4,
       'Administracja systemów i sieci komputerowych (ASiSK)'
FROM users WHERE album_number = '21004';

INSERT OR IGNORE INTO user_profiles (user_id, phone, academic_year, semester, specialization)
SELECT id, '+48 512 100 005', '2025/2026', 6,
       'Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)'
FROM users WHERE album_number = '21005';

INSERT OR IGNORE INTO user_profiles (user_id, phone, department, position)
SELECT id, '+48 55 239 31 50', 'Katedra Informatyki', 'Adiunkt'
FROM users WHERE email = 'opiekun@ans-elblag.pl';

INSERT OR IGNORE INTO user_profiles (user_id, phone, department, position)
SELECT id, '+48 55 239 31 51', 'Katedra Informatyki', 'Starszy wykładowca'
FROM users WHERE email = 'opiekun2@ans-elblag.pl';

INSERT OR IGNORE INTO user_profiles (user_id, phone, position, company_name)
SELECT id, '+48 58 123 45 67', 'Kierownik Działu IT', 'Techno Systems Sp. z o.o.'
FROM users WHERE email = 'zopz@firma.pl';


-- ──────────────────────────────────────────────────────────────
--  ROK AKADEMICKI
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO academic_years
    (year_code, start_date, end_date, practice_start_date, practice_end_date, is_current)
VALUES
    ('2023/2024', '2023-10-01', '2024-09-30', '2024-03-01', '2024-06-30', 0),
    ('2024/2025', '2024-10-01', '2025-09-30', '2025-03-01', '2025-06-30', 0),
    ('2025/2026', '2025-10-01', '2026-09-30', '2026-03-01', '2026-06-30', 1);


-- ──────────────────────────────────────────────────────────────
--  ZAKŁADY PRACY
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO companies
    (name, nip, regon, address_street, address_city, address_zip,
     representative_name, representative_position, phone, email, is_verified)
VALUES
    ('Techno Systems Sp. z o.o.',    '589-212-34-56', '220891234',
     'ul. Portowa 12',      'Gdańsk',  '80-001',
     'Piotr Zieliński',  'Prezes Zarządu',
     '+48 58 123 45 67', 'biuro@technosystems.pl', 1),

    ('DataSoft Sp. z o.o.',          '739-100-22-33', '380123456',
     'ul. Technologiczna 5', 'Olsztyn', '10-062',
     'Anna Kowalczyk',   'Dyrektor Techniczny',
     '+48 89 456 78 90', 'kontakt@datasoft.pl', 1),

    ('MediScan Sp. z o.o.',          '739-200-44-55', '380654321',
     'ul. Medyczna 22',     'Olsztyn', '10-900',
     'Tomasz Jabłoński', 'Kierownik Projektu',
     '+48 89 321 00 11', 'biuro@mediscan.pl', 1),

    ('IT Elbląg S.A.',               '578-000-11-22', '170000111',
     'ul. Browarna 90',     'Elbląg',  '82-300',
     'Rafał Wiśniewska', 'Prezes',
     '+48 55 611 22 33', 'hr@itelblag.pl', 1),

    ('SoftHouse Sp. z o.o.',         '578-100-55-66', '170123777',
     'ul. Królewiecka 17',  'Elbląg',  '82-300',
     'Monika Szymańska', 'Dyrektor ds. HR',
     '+48 55 611 44 55', 'rekrutacja@softhouse.pl', 0);


-- ──────────────────────────────────────────────────────────────
--  PRAKTYKI (internships)
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO internships
    (student_id, uopz_id, zopz_id, company_id, academic_year_id,
     agreement_number, start_date, end_date,
     status, total_hours, total_days,
     hours_completed, days_completed,
     grade_z, grade_u, grade_s,
     specialization)
VALUES
    -- Aleksandra Kowalska (21001) – zakończona, oceniona
    (
        (SELECT id FROM users WHERE album_number = '21001'),
        (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'),
        (SELECT id FROM users WHERE email = 'zopz@firma.pl'),
        (SELECT id FROM companies WHERE nip = '589-212-34-56'),
        (SELECT id FROM academic_years WHERE year_code = '2025/2026'),
        'PZ/2026/001', '2026-04-01', '2026-05-31',
        'completed', 240, 40, 240, 40,
        5.0, 5.0, 5.0,
        'Administracja systemów i sieci komputerowych (ASiSK)'
    ),
    -- Marek Nowak (21002) – w trakcie, dziennik wysłany do weryfikacji
    (
        (SELECT id FROM users WHERE album_number = '21002'),
        (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'),
        (SELECT id FROM users WHERE email = 'zopz@firma.pl'),
        (SELECT id FROM companies WHERE nip = '739-100-22-33'),
        (SELECT id FROM academic_years WHERE year_code = '2025/2026'),
        'PZ/2026/002', '2026-03-01', '2026-04-30',
        'awaiting_review', 240, 40, 120, 15,
        NULL, NULL, NULL,
        'Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)'
    ),
    -- Katarzyna Wróbel (21003) – aktywna, w trakcie praktyki
    (
        (SELECT id FROM users WHERE album_number = '21003'),
        (SELECT id FROM users WHERE email = 'opiekun2@ans-elblag.pl'),
        (SELECT id FROM users WHERE email = 'zopz@firma.pl'),
        (SELECT id FROM companies WHERE nip = '739-200-44-55'),
        (SELECT id FROM academic_years WHERE year_code = '2025/2026'),
        'PZ/2026/003', '2026-05-01', '2026-06-30',
        'active', 240, 40, 40, 5,
        NULL, NULL, NULL,
        'Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)'
    ),
    -- Piotr Zając (21004) – szkic porozumienia
    (
        (SELECT id FROM users WHERE album_number = '21004'),
        (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'),
        (SELECT id FROM users WHERE email = 'zopz@firma.pl'),
        (SELECT id FROM companies WHERE nip = '578-000-11-22'),
        (SELECT id FROM academic_years WHERE year_code = '2025/2026'),
        'PZ/2026/004', '2026-06-01', '2026-07-31',
        'draft', 240, 40, 0, 0,
        NULL, NULL, NULL,
        'Administracja systemów i sieci komputerowych (ASiSK)'
    );


-- ──────────────────────────────────────────────────────────────
--  WPISY DZIENNIKA – Aleksandra Kowalska (internship_id = 1)
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO diary_entries
    (internship_id, day_number, entry_date, hours_worked, description, status, reviewed_by)
VALUES
    (1, 1, '2026-04-01', 8,
     'Zapoznanie z infrastrukturą sieciową firmy. Uczestnictwo w odprawie z kierownikiem działu IT. Przegląd dokumentacji topologii LAN/WAN.',
     'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl')),
    (1, 2, '2026-04-02', 8,
     'Konfiguracja przełączników Cisco Catalyst serii 2960 w szafie serwerowej. Tworzenie VLAN-ów dla poszczególnych działów firmy.',
     'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl')),
    (1, 3, '2026-04-03', 8,
     'Administracja serwerami Windows Server 2022. Zarządzanie kontami użytkowników w Active Directory. Tworzenie grup zabezpieczeń.',
     'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl')),
    (1, 4, '2026-04-04', 8,
     'Konfiguracja polityk GPO (Group Policy) dla stacji roboczych. Instalacja i konfiguracja serwera WSUS do centralnego zarządzania aktualizacjami.',
     'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl')),
    (1, 5, '2026-04-07', 8,
     'Wdrożenie monitoringu infrastruktury IT przy użyciu narzędzia Zabbix. Dodawanie hostów i konfiguracja alertów dla krytycznych usług.',
     'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl'));


-- ──────────────────────────────────────────────────────────────
--  WPISY DZIENNIKA – Marek Nowak (internship_id = 2)
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO diary_entries
    (internship_id, day_number, entry_date, hours_worked, description, status)
VALUES
    (2, 1, '2026-03-03', 8,
     'Zapoznanie z architekturą systemu bazodanowego firmy. Analiza istniejących schematów PostgreSQL. Uczestnictwo w spotkaniu zespołu deweloperskiego.',
     'approved'),
    (2, 2, '2026-03-04', 8,
     'Projektowanie nowych tabel i relacji dla modułu raportowania. Implementacja migracji przy użyciu narzędzia Liquibase. Pisanie testów jednostkowych.',
     'approved'),
    (2, 3, '2026-03-05', 8,
     'Optymalizacja zapytań SQL: analiza planów wykonania (EXPLAIN ANALYZE), dodawanie brakujących indeksów, refaktoryzacja widoków bazodanowych.',
     'submitted'),
    (2, 4, '2026-03-06', 8,
     'Tworzenie procedur składowanych i funkcji w PL/pgSQL. Implementacja logiki biznesowej po stronie bazy danych. Code review z seniorem.',
     'submitted');


-- ──────────────────────────────────────────────────────────────
--  POTWIERDZENIA EFEKTÓW UCZENIA – Aleksandra Kowalska
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO outcome_confirmations
    (internship_id, learning_outcome_id, status, confirmed_by, comment)
SELECT
    1,
    lo.id,
    'achieved',
    (SELECT id FROM users WHERE email = 'zopz@firma.pl'),
    'Efekt w pełni zrealizowany w trakcie praktyki.'
FROM learning_outcomes lo;


-- ──────────────────────────────────────────────────────────────
--  SPRAWOZDANIE – Aleksandra Kowalska
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO reports
    (internship_id, section_characteristics, section_activities, section_self_assessment, status, approved_by)
VALUES
    (1,
     'Techno Systems Sp. z o.o. to firma informatyczna z Gdańska, specjalizująca się w rozwiązaniach sieciowych i systemowych dla sektora MŚP. Zatrudnia 45 pracowników w czterech działach: Infrastruktura IT, Helpdesk, Bezpieczeństwo i Sprzedaż.',
     'W trakcie praktyki konfigurowałam przełączniki sieciowe i serwery Windows Server, wdrożyłam system monitoringu Zabbix, uczestniczyłam w helpdesku technicznym oraz prowadziłam audyt bezpieczeństwa IT.',
     'Praktyka pozwoliła mi zastosować wiedzę z administracji sieciowej w realnym środowisku produkcyjnym. Szczególnie wartościowe było samodzielne zarządzanie infrastrukturą pod nadzorem doświadczonego opiekuna.',
     'approved',
     (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'));


-- ──────────────────────────────────────────────────────────────
--  ANKIETA – Aleksandra Kowalska
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO surveys
    (internship_id,
     answers,
     additional_comments,
     metadata,
     submitted_at)
VALUES
    (1,
     '[{"q_id":1,"value":5},{"q_id":2,"value":5},{"q_id":3,"value":5},{"q_id":4,"value":5},{"q_id":5,"value":5},{"q_id":6,"value":5},{"q_id":7,"value":5},{"q_id":8,"value":4},{"q_id":9,"value":5},{"q_id":10,"value":4},{"q_id":11,"value":5},{"q_id":12,"value":5},{"q_id":13,"value":4},{"q_id":14,"value":5}]',
     'Praktyka w pełni odpowiadała moim oczekiwaniom. Polecam tę firmę innym studentom.',
     '{"rok_akademicki":"2025/2026","kierunek":"Informatyka","forma":"stacjonarne","semestr":6}',
     '2026-06-02');


-- ──────────────────────────────────────────────────────────────
--  POWIADOMIENIA
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO notifications
    (recipient_id, type, title, message, link, is_read)
VALUES
    -- Powiadomienie dla studenta 21001 o zatwierdzeniu
    ((SELECT id FROM users WHERE album_number = '21001'),
     'entry_approved',
     'Wpis dziennika zatwierdzony',
     'Twój wpis z dnia 2026-04-01 został zatwierdzony przez opiekuna zakładowego.',
     '/student/21001', 1),

    -- Powiadomienie dla studenta 21002 o oczekującym wpisie
    ((SELECT id FROM users WHERE album_number = '21002'),
     'entry_approved',
     'Wpis dziennika zatwierdzony',
     'Twój wpis z dnia 2026-03-03 został zatwierdzony.',
     '/student/21002', 0),

    -- Powiadomienie dla UOPZ o nowym dokumencie
    ((SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'),
     'document_submitted',
     'Nowy dziennik do weryfikacji',
     'Student Marek Nowak przesłał dziennik do zatwierdzenia.',
     '/student/21002', 0),

    -- Powiadomienie dla studenta 21003 o zbliżającym się terminie
    ((SELECT id FROM users WHERE album_number = '21003'),
     'deadline_near',
     'Zbliża się termin złożenia dokumentów',
     'Do końca praktyki pozostało mniej niż 14 dni. Pamiętaj o wypełnieniu sprawozdania.',
     '/student/21003', 0);


-- ──────────────────────────────────────────────────────────────
--  HISTORIA LOGOWANIA (przykładowe próby)
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO login_attempts (email, ip_address, success, failure_reason) VALUES
    ('student@student.ans-elblag.pl',  '192.168.1.10', 1, NULL),
    ('student@student.ans-elblag.pl',  '192.168.1.10', 1, NULL),
    ('student2@student.ans-elblag.pl', '192.168.1.11', 0, 'wrong_password'),
    ('student2@student.ans-elblag.pl', '192.168.1.11', 0, 'wrong_password'),
    ('student2@student.ans-elblag.pl', '192.168.1.11', 1, NULL),
    ('nieznany@test.pl',               '10.0.0.5',     0, 'unknown_user');


-- ──────────────────────────────────────────────────────────────
--  LOGI AUDYTOWE
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO audit_logs
    (user_id, user_role, action, entity_type, entity_id, ip_address)
VALUES
    ((SELECT id FROM users WHERE album_number = '21001'), 'student',
     'login', 'users', (SELECT id FROM users WHERE album_number = '21001'), '192.168.1.10'),

    ((SELECT id FROM users WHERE album_number = '21001'), 'student',
     'submit', 'internships', 1, '192.168.1.10'),

    ((SELECT id FROM users WHERE email = 'zopz@firma.pl'), 'zopz',
     'approve', 'diary_entry', 1, '192.168.1.20'),

    ((SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'), 'uopz',
     'approve', 'reports', 1, '192.168.1.30'),

    ((SELECT id FROM users WHERE email = 'admin@ans-elblag.pl'), 'admin',
     'create', 'users', NULL, '192.168.1.1');


-- ──────────────────────────────────────────────────────────────
--  HISTORIA PRZEJŚĆ STATUSÓW
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO status_transitions
    (entity_type, entity_id, from_status, to_status, triggered_by, reason)
VALUES
    ('internship', 1, 'draft',    'active',
     (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'), 'Zatwierdzono porozumienie'),

    ('internship', 1, 'active',   'awaiting_review',
     (SELECT id FROM users WHERE album_number = '21001'), 'Studentka przesłała dokumenty do weryfikacji'),

    ('internship', 1, 'awaiting_review', 'completed',
     (SELECT id FROM users WHERE email = 'opiekun@ans-elblag.pl'), 'Wszystkie dokumenty zatwierdzone'),

    ('diary_entry', 1, 'draft', 'submitted',
     (SELECT id FROM users WHERE album_number = '21001'), NULL),

    ('diary_entry', 1, 'submitted', 'approved',
     (SELECT id FROM users WHERE email = 'zopz@firma.pl'), 'Wpis zgodny z programem praktyki');


-- ═══════════════════════════════════════════════════════════════
--  KONIEC DANYCH TESTOWYCH
-- ═══════════════════════════════════════════════════════════════
