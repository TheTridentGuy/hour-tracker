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
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if not user:
        user = db.user.create({
            "slack_id": slack_id
        })
    if not user.signed_in:
        db.user.update(where={
            "slack_id": slack_id
        }, data={
            "signed_in": True,
            "signin_time": datetime.datetime.now()
        })
        respond(":white_check_mark: You've been signed in.")
    else:
        respond(":x: You're already signed in.")


@app.command("/so")
@app.command("/signout")
def signout(ack, respond, command):
    ack()
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if user and user.signed_in:
        new_hours = (datetime.datetime.now() - user.signin_time.replace(tzinfo=None)).seconds / 3600
        user = db.user.update(where={
            "slack_id": slack_id
        }, data={
            "signed_in": False,
            "total_hours": user.total_hours + new_hours
        })
        respond(f":white_check_mark: You've been signed out. This session you logged {new_hours:.2f} hours, and you now have {user.total_hours:.2f} hours.")
    else:
        respond(":x: You aren't signed in.")


client.chat_postMessage(channel=MAIN_CHANNEL, text="coming soon")
SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
