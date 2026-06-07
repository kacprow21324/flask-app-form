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
    \
    # XeLaTeX – silnik + wymagane pakiety LaTeX
    texlive-xetex \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-lang-polish \
    \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
