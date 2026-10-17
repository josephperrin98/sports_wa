"""HTTP layer: receives Twilio's webhook and hands it to the service. No logic here."""

from fastapi import FastAPI, Request, Response

from app import service, whatsapp

app = FastAPI()


@app.post("/webhook/whatsapp")
async def incoming_whatsapp(request: Request) -> Response:
    message = whatsapp.parse_incoming(await request.body())
    reply = service.reply_to(message.text)
    return Response(content=whatsapp.build_reply(reply), media_type="application/xml")
