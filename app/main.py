"""HTTP layer: receives Twilio's webhook and hands it to the service. No logic here."""

import logging

from fastapi import BackgroundTasks, FastAPI, Request, Response

from app import service, whatsapp

# Without this, INFO lines (like the Claude cost log) are dropped. Cloud Run collects stderr.
logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.post("/webhook/whatsapp")
async def incoming_whatsapp(request: Request, background: BackgroundTasks) -> Response:
    message = whatsapp.parse_incoming(await request.body())
    plan = service.plan_for(message.sender, message.text)
    if plan.answer_later:
        # Runs after the response is sent, so Twilio gets its quick reply in time.
        background.add_task(service.answer, message.sender, message.text, whatsapp.send_message)
    return Response(content=whatsapp.build_reply(plan.reply_now), media_type="application/xml")
