import datetime
import os
import re
import threading
import time

import dotenv
import schedule
from flask import Flask, abort
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

os.system("prisma db push")
import prisma

db = prisma.Prisma()
db.connect()
dotenv.load_dotenv()
bot = App(token=os.environ["SLACK_BOT_TOKEN"])
api = Flask(__name__)
client = bot.client

SLACK_ADMIN_CHANNEL = os.environ["SLACK_ADMIN_CHANNEL"]
DATABASE_URL = os.environ["DATABASE_URL"]
WEDNESDAY = 2
FRIDAY = 4
FALL_START_MONTH_DAY = (8, 1)  # August 1st
FALL_END_MONTH_DAY = (1, 1)  # January 1st


is_fall = lambda: [any([FALL_START_MONTH_DAY < (today.month, today.day), (today.month, today.day) < FALL_END_MONTH_DAY]) for today in [datetime.date.today()]][0]

@bot.command("/si")
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
        admin_channel_log(f":information_source: <@{slack_id}> signed in.")
        respond(":white_check_mark: You've been signed in.")
    else:
        respond(":x: You're already signed in.  Try running `/so` to sign out.")


@bot.command("/so")
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
            "fall_total_hours" if is_fall() else "spring_total_hours": (user.fall_total_hours if is_fall() else user.spring_total_hours) + new_hours
        })
        admin_channel_log(f":information_source: <@{slack_id}> signed out.")
        respond(
            f":white_check_mark: You've been signed out. This session you logged {new_hours:.2f} hours, and you now have {user.fall_total_hours if is_fall() else user.spring_total_hours:.2f} hours this {'fall' if is_fall() else 'spring'}.")
    else:
        respond(":x: You aren't signed in. Try running `/si` to sign in.")


@bot.command("/ss")
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
            f":large_green_square: You've been signed in since {user.signin_time.replace(tzinfo=None).strftime('%H:%M')}, and have a total of {user.fall_total_hours if is_fall() else user.spring_total_hours:.2f} hours this {'fall' if is_fall() else 'spring'}.")
    else:
        respond(f":large_red_square: You're signed out, and have a total of {user.fall_total_hours if is_fall() else user.spring_total_hours:.2f} hours this {'fall' if is_fall() else 'spring'}.")


@bot.command("/hours")
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
                        "text": "Fall Hours",
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
                        "text": "Spring Hours",
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
                        "text": f"{user.fall_total_hours:.2f}"
                    }]
                }]
            }, {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{
                        "type": "text",
                        "text": f"{user.spring_total_hours:.2f}"
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


@bot.command("/amend")
def amend(ack, respond, command):
    ack()
    channel = command["channel_id"]
    slack_id = command["user_id"]
    args = command["text"].split(" ")
    if channel == SLACK_ADMIN_CHANNEL:
        try:
            assert len(args) == 2
            amendee_slack_id = re.findall(r"(?<=<@)[A-Z0-9]+", args[0])[0]
            ammendment = float(args[1])
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
                "fall_total_hours" if is_fall() else "spring_total_hours": (amendee.fall_total_hours if is_fall() else amendee.spring_total_hours) + ammendment
            })
            admin_channel_log(f":information_source: <@{slack_id}> gave <@{amendee_slack_id}> {ammendment} hours.")
            respond(f":white_check_mark: Gave <@{amendee_slack_id}> {ammendment:.2f} hours.")
        except (AssertionError, ValueError):
            respond(f":x: Unable to amend hours, you probably didn't format the command correctly.")
    else:
        respond(f":x: This can only be run in <#{SLACK_ADMIN_CHANNEL}>.")


@api.route("/api/<string:endpoint>/<string:slack_id>")
def api_hours(endpoint, slack_id):
    user = db.user.find_first(where={
        "slack_id": slack_id
    })
    if endpoint == "fall_total_hours":
        return str(user.fall_total_hours if user else 0)
    if endpoint == "spring_total_hours":
        return str(user.spring_total_hours if user else 0)
    elif endpoint == "wednesdays":
        return str(user.wednesdays if user else 0)
    elif endpoint == "fridays":
        return str(user.fridays if user else 0)
    else:
        abort(404)


def admin_channel_log(message):
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
        admin_channel_log(f":information_source: DM'ed <@{user.slack_id}> about their failure to sign out.")
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
schedule.every().day.at("07:00").do(send_backup)
schedule_loop_thread = threading.Thread(target=schedule_loop)
schedule_loop_thread.start()
slack_bot_thread = threading.Thread(target=SocketModeHandler(bot, os.environ["SLACK_APP_TOKEN"]).start)
slack_bot_thread.start()
api.run(os.environ["API_HOST"], int(os.environ["API_PORT"]))
