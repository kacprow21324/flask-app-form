FROM python:3.11-slim

WORKDIR /app

# System libraries:
#   - WeasyPrint: Cairo + Pango (nadal używane przez /drukuj w przeglądarce)
#   - XeLaTeX:    TeX Live z obsługą polskich znaków i fontów TeX Gyre
RUN apt-get update && apt-get install -y --no-install-recommends \
    \
    # WeasyPrint
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libcairo2 \
    libffi8 \
    fonts-dejavu-core \
    fonts-texgyre \
    \
    # XeLaTeX – silnik + wymagane pakiety LaTeX
    texlive-xetex \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-lang-polish \
    \
    # Bezpieczne przełączanie użytkownika w entrypoincie
    gosu \
    \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
