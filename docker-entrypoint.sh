#!/bin/sh
set -e
# Napraw uprawnienia katalogu danych – konieczne gdy bind mount z hosta
# (np. Windows/Docker Desktop) montuje katalog jako root:root.
chown -R appuser:appuser /app/data 2>/dev/null || true
exec gosu appuser "$@"
