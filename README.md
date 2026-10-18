# sports_wa

A WhatsApp bot that answers "what's on?" with a short, ranked list of live sports and the channel to watch them on. Work in progress: currently answers for Serie A only, with Claude and web search.

## Layout

- `app/whatsapp.py`: everything Twilio-specific: signature check, parsing webhooks, replies, sending messages
- `app/service.py`: decides what to reply (builds the prompt, asks Claude)
- `app/claude.py`: calls the Claude API with web search, using only the standard library
- `app/preferences.py` + `preferences.toml`: what I like to watch, turned into prompt text
- `app/main.py`: FastAPI route `POST /webhook/whatsapp`: acks at once, answers in the background
- `Dockerfile`: how Cloud Run builds and starts the app

## Run the tests

```bash
pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

## Run locally

Needs Python 3.11+. Secrets go in a `.env` file (see `.env.example`), which is never committed. Load it into the shell, then start the server:

```bash
set -a; . ./.env; set +a
uvicorn app.main:app --port 8080
```

## Deploy to Google Cloud Run

Turn the filled-in `.env` into the file format Cloud Run reads, deploy, then delete that copy:

```bash
grep -E '^[A-Z_]+=' .env | sed -E 's/^([A-Z_]+)=(.*)$/\1: "\2"/' > /tmp/sports-wa-env.yaml
gcloud run deploy sports-wa --source . --region us-east1 --no-cpu-throttling --max-instances 1 --allow-unauthenticated --env-vars-file /tmp/sports-wa-env.yaml
rm /tmp/sports-wa-env.yaml
```

`--no-cpu-throttling` keeps the CPU on after the webhook response, which the background answer needs. `--allow-unauthenticated` lets Twilio reach the URL. The app itself rejects any request without a valid Twilio signature.
