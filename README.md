# sports_wa

A WhatsApp bot that answers "what's on?" with a short, ranked list of live sports and the channel to watch them on. Work in progress: currently answers for Serie A only, with Claude and web search.

## Layout

- `app/whatsapp.py`: Twilio-specific parsing of incoming webhooks and building replies
- `app/service.py`: decides what to reply (builds the prompt, asks Claude)
- `app/claude.py`: calls the Claude API with web search, using only the standard library
- `app/preferences.py` + `preferences.toml`: what I like to watch, turned into prompt text
- `app/main.py`: FastAPI route `POST /webhook/whatsapp` that connects the two

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
