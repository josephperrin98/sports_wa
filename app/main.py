"""HTTP layer: receives Twilio's webhook and hands it to the service. No logic here."""

import asyncio
import logging

from fastapi import FastAPI, Request, Response

from app import service, whatsapp

# Without this, INFO lines (like the Claude cost log) are dropped. Cloud Run collects stderr.
logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.post("/webhook/whatsapp")
async def incoming_whatsapp(request: Request) -> Response:
    message = whatsapp.parse_incoming(await request.body())
    # The Claude call blocks for up to a minute. Running it in a worker thread keeps the
    # server free to handle other requests in the meantime.
    reply = await asyncio.to_thread(service.reply_to, message.text)
    return Response(content=whatsapp.build_reply(reply), media_type="application/xml")
