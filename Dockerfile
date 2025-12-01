# Verwende ein leichtes Python 3.10 Image als Basis
FROM python:3.10-slim

# Arbeitsverzeichnis im Container erstellen
WORKDIR /app

# Anforderungen kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Den Server-Code und das Template-Verzeichnis kopieren
COPY server.py .
COPY templates/ templates/
COPY static/ static/

# Ports freigeben:
# 8000 = Web Dashboard (für den Browser)
EXPOSE 8000

# Startbefehl
CMD ["python", "server.py"]
