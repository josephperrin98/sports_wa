# sports_wa

A WhatsApp bot that answers "what's on?" with a short, ranked list of live sports and the channel to watch them on. Work in progress: covers every tier in `preferences.toml` plus a wildcard sport, with Claude and web search.

## How a question is answered

Claude takes 30-40 seconds, longer than Twilio waits for a reply, and a Twilio trial account can't send a message later. So:

1. "what's on?" gets "On it..." straight away, and the search starts in the background.
2. Any next message collects the answer (or "Still checking" if it isn't ready yet).

## Layout

- `app/whatsapp.py`: everything Twilio-specific: signature check, parsing webhooks, replies
- `app/service.py`: decides what to reply (builds the prompt, asks Claude, keeps the answer until it's collected)
- `app/claude.py`: calls the Claude API with web search, using only the standard library
- `app/preferences.py` + `preferences.toml`: what I like to watch, turned into prompt text
- `app/evaluation.py`: turns the answer log into a CSV sheet for checking answers by hand
- `app/main.py`: FastAPI route `POST /webhook/whatsapp`: replies at once, searches in the background
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

`--no-cpu-throttling` keeps the CPU on after the webhook response, which the background search needs. `--max-instances 1` keeps the waiting answer and the next message in the same process. `--allow-unauthenticated` lets Twilio reach the URL. The app itself rejects any request without a valid Twilio signature.

After a code-only change, `gcloud run deploy sports-wa --source . --region us-east1` is enough: the new version keeps the settings and flags of the last one.

## Evaluation

Every answer is logged as one line in Cloud Logging (kept 30 days): the time, the question, the wildcard region and the reply. To get them as a sheet, in Cloud Shell from the project folder:

```bash
gcloud logging read 'resource.labels.service_name="sports-wa" AND textPayload:"answer_log"' --freshness=30d --format=json | python3 -m app.evaluation > answers.csv
```

`cloudshell download answers.csv` saves it to your computer; open it in any spreadsheet. `events_listed` and `has_wildcard` are counted from the reply. Fill in the rest after checking each answer against the broadcaster's TV guide or the league's "where to watch" page:

- `events_on_today`: how many listed events really were live or on later that day
- `channels_correct`: how many listed events had their main channel right
- `ranking_ok`: y or n, whether the order felt right
- `wildcard_watchable`: y or n, whether the wildcard's `Watch:` line really showed it
- `notes`: anything wrong, in a few words

The cost of each answer is in the `claude ...` log line written just before it.
