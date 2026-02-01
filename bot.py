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
ADMINS = set()
BANNED = set()
LOCKED = False
# =====================


def is_owner(uid):
    return uid in OWNERS


def is_admin(uid):
    return uid in ADMINS or is_owner(uid)


@handler.add(MessageEvent, message=TextMessage)
def control(event):

    global LOCKED

    user_id = event.source.user_id
    text = event.message.text.strip()
    group_id = event.source.group_id


    # 🔥 وضع الطوارئ
    if LOCKED and not is_admin(user_id):
        return


    # ==================
    # رفع ادمن
    # ==================
    if text.startswith("رفع") and is_owner(user_id):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                ADMINS.add(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم رفعه ادمن")
        )


    # ==================
    # تنزيل ادمن
    # ==================
    if text.startswith("تنزيل") and is_owner(user_id):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                ADMINS.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("❌ تم تنزيل الادمن")
        )


    # ==================
    # رفع اونر
    # ==================
    if text.startswith("اونر") and is_owner(user_id):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                OWNERS.append(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("👑 تم رفع Owner")
        )


    # ==================
    # حظر
    # ==================
    if text.startswith("حظر") and is_admin(user_id):

        if event.message.mention:
            for m in event.message.mention.mentionees:

                if is_owner(m.user_id):
                    continue

                BANNED.add(m.user_id)

                try:
                    line_bot_api.kickout_from_group(
                        group_id,
                        [m.user_id]
                    )
                except:
                    pass

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚫 تم حظر العضو")
        )


    # ==================
    # فك الحظر
    # ==================
    if text.startswith("فك") and is_owner(user_id):

        if event.message.mention:
            for m in event.message.mention.mentionees:
                BANNED.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم فك الحظر")
        )


    # ==================
    # قفل الجروب
    # ==================
    if text == "قفل" and is_admin(user_id):
        LOCKED = True

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔒 تم قفل الجروب (وضع الطوارئ)")
        )


    # ==================
    # فتح الجروب
    # ==================
    if text == "فتح" and is_admin(user_id):
        LOCKED = False

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔓 تم فتح الجروب")
        )


    # ==================
    # منع @all
    # ==================
    if "@all" in text and not is_admin(user_id):

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚫 ممنوع استخدام @all")
        )


# 🔥 منع دخول المحظورين
@handler.add(MemberJoinedEvent)
def anti_ban(event):

    group_id = event.source.group_id

    for member in event.joined.members:

        if member.user_id in BANNED:

            try:
                line_bot_api.kickout_from_group(
                    group_id,
                    [member.user_id]
                )
            except:
                pass


if __name__ == "__main__":
    app.run(port=5000)


