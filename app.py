import datetime
import os
import re
import threading
import time

import dotenv
import schedule
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

os.system("prisma db push")
import prisma

db = prisma.Prisma()
db.connect()
dotenv.load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = app.client

SLACK_ADMIN_CHANNEL = os.environ["SLACK_ADMIN_CHANNEL"]
DATABASE_URL = os.environ["DATABASE_URL"]
WEDNESDAY = 2
FRIDAY = 4


@app.command("/si")
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
        respond(":x: You're already signed in.  Try running `/so` to sign out.")


@app.command("/so")
def signout(ack, respond, command):
    ack()
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if user and user.signed_in:
        new_hours = (datetime.datetime.now() - user.signin_time.replace(tzinfo=None)).seconds / 3600
        signin_weekday = user.signin_time.weekday()
        if signin_weekday in [WEDNESDAY, FRIDAY] and (
                not user.last_special_day or not user.signin_time.date() == user.last_special_day.date()):
            if signin_weekday == WEDNESDAY:
                user = db.user.update(where={
                    "slack_id": slack_id,
                }, data={
                    "wednesdays": user.wednesdays + 1,
                    "last_special_day": datetime.datetime.now()
                })
            else:
                user = db.user.update(where={
                    "slack_id": slack_id,
                }, data={
                    "fridays": user.fridays + 1,
                    "last_special_day": datetime.datetime.now()
                })
        user = db.user.update(where={
            "slack_id": slack_id
        }, data={
            "signed_in": False,
            "total_hours": user.total_hours + new_hours
        })
        log(f":information_source: <@{slack_id}> signed out.")
        respond(
            f":white_check_mark: You've been signed out. This session you logged {new_hours:.2f} hours, and you now have {user.total_hours:.2f} hours.")
    else:
        respond(":x: You aren't signed in. Try running `/si` to sign in.")


@app.command("/ss")
def signin_status(ack, respond, command):
    ack()
    slack_id = command["user_id"]
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if user is None:
        respond(":bangbang: You've never signed in your life. Try running `/si` to sign in.")
    elif user.signed_in:
        respond(
            f":large_green_square: You've been signed in since {user.signin_time.replace(tzinfo=None).strftime('%H:%M')}, and have a total of {user.total_hours:.2f} hours.")
    else:
        respond(f":large_red_square: You're signed out, and have a total of {user.total_hours:.2f} hours.")


@app.command("/hours")
def hours(ack, respond, command):
    ack()
    slack_id = command["user_id"]
    channel = command["channel_id"]
    if channel == SLACK_ADMIN_CHANNEL:
        users = db.user.find_many()
        blocks = [{
            "type": "table",
            "rows": [[{
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": "Signed In?",
                        "style": {
                            "bold": True
                        }
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": "User",
                        "style": {
                            "bold": True
                        }
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": "Hours",
                        "style": {
                            "bold": True
                        }
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": "Wednesdays",
                        "style": {
                            "bold": True
                        }
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": "Fridays",
                        "style": {
                            "bold": True
                        }
                    }]
                }]
            }]] + [[{
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "emoji",
                        "name": "large_green_square" if user.signed_in else "large_red_square"
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "user",
                        "user_id": user.slack_id
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": f"{user.total_hours:.2f}"
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": f"{user.wednesdays}"
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": f"{user.fridays}"
                    }]
                }]
            }] for user in users]
        }, {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Triggered with `/hours` by <@{slack_id}>"
            }]
        }]
        client.chat_postMessage(channel=SLACK_ADMIN_CHANNEL, text="Hour Report", blocks=blocks)
    else:
        respond(f":x: This can only be run in <#{SLACK_ADMIN_CHANNEL}>.")


@app.command("/amend")
def amend(ack, respond, command):
    ack()
    channel = command["channel_id"]
    slack_id = command["user_id"]
    args = command["text"].split(" ")
    if channel == SLACK_ADMIN_CHANNEL:
        try:
            assert len(args) == 2
            amendee_slack_id = re.findall(r"(?<=<@)[A-Z0-9]+", args[0])[0]
            ammendement = float(args[1])
            amendee = db.user.find_first(where={
                "slack_id": amendee_slack_id
            })
            if not amendee:
                amendee = db.user.create({
                    "slack_id": slack_id
                })
            db.user.update(where={
                "slack_id": amendee_slack_id
            }, data={
                "total_hours": amendee.total_hours + ammendement
            })
            log(f":information_source: <@{slack_id}> gave <@{amendee_slack_id}> {ammendement} hours.")
            respond(f":white_check_mark: Gave <@{amendee_slack_id}> {ammendement:.2f} hours.")
        except (AssertionError, ValueError):
            respond(f":x: Unable to amend hours, you probably didn't format the command correctly.")
    else:
        respond(f":x: This can only be run in <#{SLACK_ADMIN_CHANNEL}>.")


def log(message):
    client.chat_postMessage(channel=SLACK_ADMIN_CHANNEL, text=message)


def signout_all_users():
    users = db.user.find_many(where={
        "signed_in": True,
        "signin_time": {
            "lte": datetime.datetime.now() - datetime.timedelta(hours=12)
        }
    })
    for user in users:
        db.user.update(where={
            "slack_id": user.slack_id
        }, data={
            "signed_in": False
        })
        log(f":information_source: DM'ed <@{user.slack_id}> about their failure to sign out.")
        client.chat_postMessage(channel=user.slack_id,
                                text=":man-facepalming: Hi, you forgot to sign out. Better luck next time!")


def send_backup():
    assert DATABASE_URL.startswith("file:")
    database_path = DATABASE_URL[5:]
    client.files_upload_v2(channel=SLACK_ADMIN_CHANNEL, file=database_path)


def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)


schedule.every().minute.do(signout_all_users)
schedule.every().day.at("00:00").do(send_backup)
schedule_loop_thread = threading.Thread(target=schedule_loop)
schedule_loop_thread.start()
SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
