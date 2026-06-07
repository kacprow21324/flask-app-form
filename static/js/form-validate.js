/* Walidacja „na bieżąco" formularzy (.page-form).
   Reguły są odbiciem core/validators.py — serwer i tak waliduje ponownie. */
(function () {
    if (!document.querySelector('.page-form')) return;

    var DIARY_MIN_LEN = 100;

    function fullName(v) {
        v = (v || "").trim();
        if (!v) return [false, "Pole jest wymagane."];
        var t = v.split(/\s+/);
        if (t.length < 2) return [false, "Podaj imię i nazwisko (min. dwa wyrazy)."];
        for (var i = 0; i < t.length; i++) {
            if (t[i].length < 2) return [false, "Każdy człon min. 2 znaki."];
            if (!/^[\p{L}'-]+$/u.test(t[i])) return [false, "Tylko litery, łącznik i apostrof (bez cyfr)."];
        }
        return [true, "Wygląda dobrze."];
    }
    function album(v) {
        v = (v || "").trim();
        if (!v) return [false, "Pole jest wymagane."];
        if (!/^\d+$/.test(v)) return [false, "Tylko cyfry."];
        if (v.length < 4 || v.length > 6) return [false, "Od 4 do 6 cyfr."];
        return [true, "OK."];
    }
    function nip(v) {
        v = (v || "").trim();
        if (!v) return [true, ""]; // opcjonalne
        var d = v.replace(/[-\s]/g, "");
        if (!/^\d{10}$/.test(d)) return [false, "NIP to 10 cyfr."];
        var w = [6, 5, 7, 2, 3, 4, 5, 6, 7], s = 0;
        for (var i = 0; i < 9; i++) s += parseInt(d[i], 10) * w[i];
        var c = s % 11;
        if (c === 10 || c !== parseInt(d[9], 10)) return [false, "Błędna suma kontrolna NIP."];
        return [true, "NIP poprawny."];
    }
    function email(v) {
        v = (v || "").trim();
        if (!v) return [false, "Adres e-mail jest wymagany."];
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) {
            return [false, "Podaj poprawny adres e-mail."];
        }
        return [true, ""];
    }
    function diaryDay(v) {
        var value = Number(v);
        if (!Number.isInteger(value) || value < 1 || value > 120) {
            return [false, "Numer dnia musi mieścić się w zakresie 1-120."];
        }
        return [true, ""];
    }
    function diaryHours(v) {
        var value = Number(v);
        if (!Number.isInteger(value) || value < 1 || value > 8) {
            return [false, "Liczba godzin musi mieścić się w zakresie 1-8."];
        }
        return [true, ""];
    }
    function diaryOpis(v) {
        v = (v || "").trim();
        if (!v) return [false, "Opis wymagany."];
        if (v.length < DIARY_MIN_LEN) return [false, "Za krótki (min. " + DIARY_MIN_LEN + ", jest " + v.length + ")."];
        return [true, ""];
    }

    function msgEl(field) {
        var el = field._vmsg;
        if (!el) {
            el = document.createElement('div');
            el.className = 'vmsg';
            field.insertAdjacentElement('afterend', el);
            field._vmsg = el;
        }
        return el;
    }
    function paint(field, res) {
        var el = msgEl(field);
        var ok = res[0];
        // Pokazujemy WYŁĄCZNIE błędy – poprawne dane nie dostają żadnego komunikatu.
        if (ok) { el.textContent = ''; el.className = 'vmsg'; field.classList.remove('field-invalid'); return; }
        el.textContent = '✗ ' + res[1];
        el.className = 'vmsg vmsg-err';
        field.classList.add('field-invalid');
    }
    function bind(field, fn) {
        if (!field) return;
        var run = function () { paint(field, fn(field.value)); };
        field.addEventListener('input', run);
        field.addEventListener('blur', run);
        if (field.value) run();
    }

    document.querySelectorAll('[name="imie_nazwisko"]').forEach(function (f) { bind(f, fullName); });
    document.querySelectorAll('[name="nr_albumu"]').forEach(function (f) { bind(f, album); });
    document.querySelectorAll('[name="nip_zakladu"]').forEach(function (f) { bind(f, nip); });
    document.querySelectorAll('input[type="email"]').forEach(function (f) { bind(f, email); });
    document.querySelectorAll('.day-input').forEach(function (f) { bind(f, diaryDay); });
    document.querySelectorAll('.hours-input').forEach(function (f) { bind(f, diaryHours); });
    document.querySelectorAll('textarea[name="opis[]"]').forEach(function (f) { bind(f, diaryOpis); });

    // Zakres dat
    var ds = document.querySelector('[name="data_start"]');
    var de = document.querySelector('[name="data_end"]');
    if (ds && de) {
        var checkRange = function () {
            if (ds.value && de.value && de.value < ds.value) {
                paint(de, [false, "Data zakończenia musi być po dacie rozpoczęcia."]);
            } else if (de.value) {
                paint(de, [true, "OK."]);
            }
        };
        ds.addEventListener('input', checkRange);
        de.addEventListener('input', checkRange);
        de.addEventListener('blur', checkRange);
        checkRange();
    }

    // Walidacja przy wysyłce – pierwszego błędnego pola dotyka focus
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            var bad = form.querySelector('.field-invalid');
            if (bad) { e.preventDefault(); bad.focus(); bad.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
        });
    });
})();
