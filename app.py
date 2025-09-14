import datetime
import os
import dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import prisma


dotenv.load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = app.client
db = prisma.Prisma()
db.connect()


MAIN_CHANNEL = os.environ["SLACK_MAIN_CHANNEL"]


@app.command("/si")
@app.command("/signin")
def signin(ack, respond, command):
    ack()
    print(command)
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if not user:
        user = db.user.create({
            "slack_id": slack_id
        })
    if not user.signed_in:
        user.signed_in = True
    else:
        respond(":x: You're already signed in!")

client.chat_postMessage(channel=MAIN_CHANNEL, text="coming soon")
SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
