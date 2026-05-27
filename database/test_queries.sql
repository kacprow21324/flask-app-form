-- ═══════════════════════════════════════════════════════════════
--  ZAPYTANIA TESTOWE – System EMS (ems.db)
--  Uruchom w DBeaver: SQL Editor → F3, wklej, zaznacz blok, Ctrl+Enter
--  Baza: instance/ems.db  (tabele: users, learning_effects)
-- ═══════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 1: PRZEGLĄD UŻYTKOWNIKÓW
-- ──────────────────────────────────────────────────────────────

-- 1.1 Wszyscy użytkownicy (bez hasła)
SELECT id,
       email,
       first_name || ' ' || last_name AS imie_nazwisko,
       role,
       album_number,
       is_active,
       last_login_at
FROM users
ORDER BY role, last_name;


-- 1.2 Tylko aktywne konta studentów
SELECT id, email, first_name, last_name, album_number
FROM users
WHERE role = 'student'
  AND is_active = 1
ORDER BY album_number;


-- 1.3 Liczba kont według roli
SELECT role,
       COUNT(*) AS liczba_kont,
       SUM(is_active) AS aktywne,
       COUNT(*) - SUM(is_active) AS zablokowane
FROM users
GROUP BY role
ORDER BY liczba_kont DESC;


-- 1.4 Konta, które nigdy się nie logowały
SELECT email, role, first_name || ' ' || last_name AS imie_nazwisko
FROM users
WHERE last_login_at IS NULL
ORDER BY role;


-- 1.5 Czy email studenta 21001 istnieje?
SELECT id, email, role, album_number, is_active
FROM users
WHERE album_number = '21001';


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 2: EFEKTY UCZENIA SIĘ
-- ──────────────────────────────────────────────────────────────

-- 2.1 Wszystkie 13 efektów (skrócony opis)
SELECT nr,
       SUBSTR(opis, 1, 80) || '...' AS skrot_opisu
FROM learning_effects
ORDER BY nr;


-- 2.2 Efekty z numerami od 1 do 5 (zakres wiedzy)
SELECT nr, opis
FROM learning_effects
WHERE nr BETWEEN 1 AND 5;


-- 2.3 Liczba efektów w bazie (powinno być 13)
SELECT COUNT(*) AS liczba_efektow FROM learning_effects;


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 3: KONTROLE DANYCH (sprawdzenie spójności)
-- ──────────────────────────────────────────────────────────────

-- 3.1 Studenci bez numeru albumu (błąd danych)
SELECT id, email, first_name, last_name
FROM users
WHERE role = 'student'
  AND (album_number IS NULL OR album_number = '');


-- 3.2 Duplikaty numerów albumów (powinno być puste)
SELECT album_number, COUNT(*) AS ile
FROM users
WHERE album_number IS NOT NULL
GROUP BY album_number
HAVING COUNT(*) > 1;


-- 3.3 Duplikaty e-mail (powinno być puste)
SELECT email, COUNT(*) AS ile
FROM users
GROUP BY email
HAVING COUNT(*) > 1;


-- 3.4 Konta z błędną rolą (powinno być puste)
SELECT id, email, role
FROM users
WHERE role NOT IN ('student', 'uopz', 'zopz', 'dziekanat', 'admin');


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 4: OPERACJE MODYFIKUJĄCE (do testów – ostrożnie!)
-- ──────────────────────────────────────────────────────────────

-- 4.1 Zmiana hasła (przykład – NIE uruchamiaj produkcyjnie,
--     hasło musi być zahaszowane przez Werkzeug/Bcrypt w Pythonie)
-- UPDATE users SET password_hash = '...' WHERE email = 'student@student.ans-elblag.pl';


-- 4.2 Dezaktywacja konta (blokada logowania)
-- UPDATE users SET is_active = 0 WHERE email = 'student2@student.ans-elblag.pl';


-- 4.3 Przywrócenie konta
-- UPDATE users SET is_active = 1, failed_login_attempts = 0 WHERE email = 'student2@student.ans-elblag.pl';


-- 4.4 Zmiana roli (awans na admina)
-- UPDATE users SET role = 'admin' WHERE email = 'student@student.ans-elblag.pl';


-- 4.5 Reset licznika błędnych logowań (odblokowanie po blokadzie)
-- UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE failed_login_attempts > 0;


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 5: STATYSTYKI SUMARYCZNE
-- ──────────────────────────────────────────────────────────────

-- 5.1 Podsumowanie bazy
SELECT
    (SELECT COUNT(*) FROM users)                         AS wszyscy_uzytkownicy,
    (SELECT COUNT(*) FROM users WHERE role = 'student')  AS studenci,
    (SELECT COUNT(*) FROM users WHERE is_active = 1)     AS aktywne_konta,
    (SELECT COUNT(*) FROM learning_effects)              AS efekty_uczenia;


-- 5.2 Najnowsze konta (ostatnie 5 utworzonych)
SELECT id, email, role, created_at
FROM users
ORDER BY created_at DESC
LIMIT 5;


-- 5.3 Konta pracownicze (UOPZ, ZOPZ, dziekanat, admin)
SELECT role,
       first_name || ' ' || last_name AS imie_nazwisko,
       email,
       is_active
FROM users
WHERE role != 'student'
ORDER BY role, last_name;


-- ──────────────────────────────────────────────────────────────
--  SEKCJA 6: WYSZUKIWANIE
-- ──────────────────────────────────────────────────────────────

-- 6.1 Znajdź użytkownika po fragmencie nazwiska
SELECT id, email, first_name, last_name, role
FROM users
WHERE last_name LIKE '%ow%'   -- zmień '%ow%' na szukany fragment
ORDER BY last_name;


-- 6.2 Znajdź efekt po słowie kluczowym
SELECT nr, opis
FROM learning_effects
WHERE opis LIKE '%dokumentacj%'  -- zmień szukane słowo
ORDER BY nr;


-- 6.3 Znajdź studenta po numerze albumu (szybkie sprawdzenie)
SELECT id, email, first_name, last_name, is_active
FROM users
WHERE album_number = '21001';   -- zmień numer albumu
