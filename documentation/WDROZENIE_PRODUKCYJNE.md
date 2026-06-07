# Wdrożenie produkcyjne

## Wymagania

- serwer Linux z Docker Engine i Docker Compose;
- domena wskazująca na serwer;
- certyfikat TLS w `deploy/certs/fullchain.pem` i klucz w
  `deploy/certs/privkey.pem`;
- aplikacja zarejestrowana jako single-tenant w Microsoft Entra ID.

## Microsoft Entra ID

1. W Microsoft Entra admin center utwórz rejestrację aplikacji obsługującą
   wyłącznie konta w katalogu uczelni.
2. Dodaj platformę `Web` i dokładny redirect URI:
   `https://DOMENA/auth/microsoft/callback`.
3. Utwórz sekret klienta i zapisz jego wartość poza repozytorium.
4. W `.env.production` ustaw `MS_CLIENT_ID`, `MS_CLIENT_SECRET`,
   `MS_TENANT_ID`, `MS_REDIRECT_URI` i `MS_ALLOWED_EMAIL_DOMAINS`.
5. Konto musi wcześniej istnieć w tabeli `users`, np. po imporcie CSV.
   Pierwsze logowanie wiąże je z niezmiennym identyfikatorem `tid + oid`.

Dokumentacja Microsoft:

- https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc
- https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference
- https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-redirect-uri

## Uruchomienie

```sh
cp .env.production.example .env.production
# uzupełnij wszystkie sekrety oraz domeny
docker compose --env-file .env.production -f docker-compose.prod.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

MariaDB i MongoDB nie mają mapowania portów hosta. Publiczne są wyłącznie
porty 80 i 443 Nginx. Prometheus nasłuchuje tylko na `127.0.0.1:9090`.

## Monitoring

- liveness: `/health/live`;
- readiness MariaDB + MongoDB: `/health/ready`;
- metryki Prometheus: `/metrics`, dostępne tylko w sieci wewnętrznej;
- reguły alertów: `deploy/alert-rules.yml`;
- logi aplikacji są zapisywane jako JSON i zawierają `X-Request-ID`.

Do wysyłania powiadomień należy podłączyć Alertmanager lub zewnętrzny system
monitoringu do alertów Prometheus.

## Backup i odtwarzanie

```sh
ENV_FILE=.env.production deploy/backup.sh
deploy/verify-restore.sh backups/20260607T120000Z
```

Backup obejmuje MariaDB, MongoDB oraz cały `/app/data`, czyli uploady,
wygenerowane PDF-y i pakiety archiwalne. `verify-restore.sh` sprawdza sumy
kontrolne i odtwarza obie bazy do jednorazowych kontenerów.

Zalecany harmonogram:

- backup codziennie;
- kopia poza serwerem codziennie po backupie;
- test odtworzenia co najmniej raz w miesiącu;
- kontrola alertów i miejsca na dysku co najmniej raz w tygodniu.

Usługa `retention` uruchamia zadanie retencji i anonimizacji raz na dobę.
