# sports_wa

A WhatsApp bot that answers "what's on?" with a short, ranked list of live sports and the channel to watch them on. Work in progress: currently an echo bot.

## Layout

- `app/whatsapp.py`: Twilio-specific parsing of incoming webhooks and building replies
- `app/service.py`: decides what to reply
- `app/main.py`: FastAPI route `POST /webhook/whatsapp` that connects the two

## Run the tests

```bash
pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

## Run locally

```bash
uvicorn app.main:app --port 8080
```

Secrets go in a `.env` file (see `.env.example`), which is never committed.
