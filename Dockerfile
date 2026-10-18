# How Cloud Run builds and starts the app.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY preferences.toml .

# Cloud Run says which port to listen on through $PORT.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
