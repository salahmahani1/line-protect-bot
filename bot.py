from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

from linebot.models import *

# ====== SETTINGS ======
OWNERS = ["U55fb450e06025fe8a329ed942e65de04"]
# 🛡️ الادمنز
ADMINS = set()

# 🚫 المحظورين
BANNED = set()

# 🔒 وضع القفل
LOCKED = False


def is_owner(uid):
    return uid in OWNERS


def is_admin(uid):
    return uid in ADMINS or uid in OWNERS


###################################
# 🔥 اوامر التحكم
###################################

@handler.add(MessageEvent, message=TextMessage)
def control(event):

    global LOCKED

    user = event.source.user_id
    text = event.message.text
    group = getattr(event.source, "group_id", None)

    if not group:
        return


    # 🔥 اختبار
    if text == "ping":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔥 بوت التحكم شغال!")
        )


    # 🔒 قفل الطوارئ
    if LOCKED and not is_admin(user):
        return


    ###################################
    # رفع ادمن
    ###################################
    if text == "رفع ادمن" and is_owner(user):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                ADMINS.add(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم رفع ادمن")
        )


    ###################################
    # تنزيل ادمن
    ###################################
    if text == "تنزيل ادمن" and is_owner(user):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                ADMINS.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("❌ تم تنزيل الادمن")
        )


    ###################################
    # حظر
    ###################################
    if text == "حظر" and is_admin(user):

        if event.message.mention:
            for m in event.message.mention.mentionees:

                if is_owner(m.user_id):
                    continue

                BANNED.add(m.user_id)

                try:
                    line_bot_api.kickout_from_group(group, [m.user_id])
                except:
                    pass

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚫 تم حظر العضو")
        )


    ###################################
    # فك الحظر
    ###################################
    if text == "فك حظر" and is_owner(user):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                BANNED.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم فك الحظر")
        )


    ###################################
    # قفل الجروب
    ###################################
    if text == "قفل" and is_admin(user):
        LOCKED = True

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔒 تم قفل الجروب")
        )


    ###################################
    # فتح الجروب
    ###################################
    if text == "فتح" and is_admin(user):
        LOCKED = False

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔓 تم فتح الجروب")
        )


    ###################################
    # منع @all
    ###################################
    if "@all" in text and not is_admin(user):

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚫 ممنوع استخدام @all")
        )


###################################
# 🔥 منع دخول المحظورين
###################################

@handler.add(MemberJoinedEvent)
def anti_banned(event):

    group = event.source.group_id

    for member in event.joined.members:

        if member.user_id in BANNED:
            try:
                line_bot_api.kickout_from_group(group, [member.user_id])
            except:
                pass

if __name__ == "__main__":
    app.run(port=5000)



