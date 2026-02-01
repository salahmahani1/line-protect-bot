from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
import time

app = Flask(__name__)

TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

############################
# 👑 الاونرز
############################

owners = {"U55fb450e06025fe8a329ed942e65de04"}

from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
import time

app = Flask(__name__)

TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

############################

owners = {"U55fb450e06025fe8a329ed942e65de04"}
admins = set()

whitelist = set(owners)
banned = set()

raid_mode = False
spam = {}

############################

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'


###################################
# الرسائل
###################################

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    global raid_mode

    user = event.source.user_id
    msg = event.message.text.lower()
    group = getattr(event.source, "group_id", None)

    if not group:
        return

    ###################################
    # Anti Spam
    ###################################

    now = time.time()

    if user not in spam:
        spam[user] = []

    spam[user].append(now)
    spam[user] = [t for t in spam[user] if now - t < 5]

    if len(spam[user]) > 5 and user not in whitelist:
        try:
            line_bot_api.kickout_from_group(group, [user])
        except:
            pass
        return

    ###################################
    # منع @all
    ###################################

    if "@all" in msg and user not in whitelist:
        try:
            line_bot_api.kickout_from_group(group, [user])
        except:
            pass
        return

    ###################################
    # البوت يرد على الادارة فقط
    ###################################

    if user not in owners and user not in admins:
        return


    ###################################
    # Alive
    ###################################

    if msg in ["alive", "ping"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔥 البوت شغال تمام")
        )
        return


    ###################################
    # Lockdown
    ###################################

    if msg == "lockdown" and user in owners:
        raid_mode = True

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚨 تم قفل الجروب!")
        )
        return


    if msg == "unlock" and user in owners:
        raid_mode = False

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم فتح الجروب.")
        )
        return


    ###################################
    # رفع ادمن بالمنشن
    ###################################

    if msg == "!admin" and user in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.add(m.user_id)
                whitelist.add(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔥 تم رفع ادمن.")
        )
        return


    ###################################
    # تنزيل ادمن
    ###################################

    if msg == "!unadmin" and user in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم تنزيل الادمن.")
        )
        return


    ###################################
    # Kick
    ###################################

    if msg == "!kick":

        if event.message.mention:
            for m in event.message.mention.mentionees:

                if m.user_id in whitelist:
                    continue

                try:
                    line_bot_api.kickout_from_group(group, [m.user_id])
                except:
                    pass
        return


    ###################################
    # Ban
    ###################################

    if msg == "!ban":

        if event.message.mention:
            for m in event.message.mention.mentionees:

                if m.user_id in whitelist:
                    continue

                banned.add(m.user_id)

                try:
                    line_bot_api.kickout_from_group(group, [m.user_id])
                except:
                    pass
        return


###################################
# منع دخول المبندين + وقت الطوارئ
###################################

@handler.add(MemberJoinedEvent)
def anti_join(event):

    group = event.source.group_id

    for m in event.joined.members:

        if raid_mode or m.user_id in banned:
            try:
                line_bot_api.kickout_from_group(group, [m.user_id])
            except:
                pass


###################################
# قفل QR
###################################

@handler.add(JoinEvent)
def lock_qr(event):

    try:
        line_bot_api.update_group(
            group_id=event.source.group_id,
            prevent_join_by_ticket=True
        )
    except:
        pass


###################################

if __name__ == "__main__":
    app.run(port=5000)