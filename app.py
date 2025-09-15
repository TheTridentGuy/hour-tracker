import datetime
import os
import dotenv
import schedule
import time
import threading
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


os.system("prisma db push")
import prisma
db = prisma.Prisma()
db.connect()
dotenv.load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = app.client


SLACK_MAIN_CHANNEL = os.environ["SLACK_MAIN_CHANNEL"]
SLACK_ADMIN_CHANNEL = os.environ["SLACK_ADMIN_CHANNEL"]
DATABASE_URL = os.environ["DATABASE_URL"]


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
        log(f":information_source: <@{slack_id}> signed in.")
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
        log(f":information_source: <@{slack_id}> signed out.")
        respond(f":white_check_mark: You've been signed out. This session you logged {new_hours:.2f} hours, and you now have {user.total_hours:.2f} hours.")
    else:
        respond(":x: You aren't signed in.")


@app.command("/ss")
@app.command("/signin-status")
def signin_status(ack, respond, command):
    ack()
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if user is None:
        respond(":bangbang: You've never signed in your life.")
    elif user.signed_in:
        respond(f":large_green_square: You've been signed in since {user.signin_time.strftime('%H:%M')}, and have a total of {user.total_hours:.2f} hours.")
    else:
        respond(f":large_red_square: You're signed out, and have a total of {user.total_hours:.2f} hours.")


def log(message):
    client.chat_postMessage(channel=SLACK_ADMIN_CHANNEL, text=message)


def signout_all_users():
    users = db.user.find_many(where={
        "signed_in": True
    })
    for user in users:
        db.user.update(where={
            "slack_id": user.slack_id
        }, data={
            "signed_in": False
        })
        client.chat_postMessage(channel=user.slack_id, text=":clown_face: Hi, you forgot to sign out today. Better luck next time!")


def send_backup():
    assert DATABASE_URL.startswith("file:")
    database_path = DATABASE_URL[5:]
    client.files_upload_v2(channel=SLACK_ADMIN_CHANNEL, file=database_path)


def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(60)


schedule.every().day.at("00:00").do(signout_all_users)
schedule.every().day.at("00:00").do(send_backup)
schedule_loop_thread = threading.Thread(target=schedule_loop)
schedule_loop_thread.start()
SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
