import os
import random
import cloudinary
import cloudinary.uploader

from flask import Flask, request, abort
from pymongo import MongoClient

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

# ================= CONFIG =================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
MONGO_URI = os.getenv("MONGO_URI")

CLOUD_NAME = os.getenv("CLOUD_NAME")
CLOUD_KEY = os.getenv("CLOUD_KEY")
CLOUD_SECRET = os.getenv("CLOUD_SECRET")

OWNER_ID = os.getenv("OWNER_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

client = MongoClient(MONGO_URI)
db = client["linebot"]

commands = db["commands"]
admins = db["admins"]
owners = db["owners"]
banned_names = db["banned"]

# اول Owner تلقائي
if OWNER_ID and not owners.find_one({"user": OWNER_ID}):
    owners.insert_one({"user": OWNER_ID})

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=CLOUD_KEY,
    api_secret=CLOUD_SECRET
)

app = Flask(__name__)
waiting = {}

# ================= HELPERS =================

def get_group_id(event):
    if event.source.type == "group":
        return event.source.group_id
    elif event.source.type == "room":
        return event.source.room_id
    return None


def is_owner(user):
    return owners.find_one({"user": user})


def is_admin(user):
    return admins.find_one({"user": user}) or is_owner(user)


def banned(trigger):
    for b in banned_names.find():
        if b["name"] in trigger:
            return True
    return False


# ================= WEBHOOK =================

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================= TEXT =================

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):

    group_id = get_group_id(event)
    if not group_id:
        return

    user_id = event.source.user_id
    text = event.message.text.strip()

    # ========= OWNER =========

    if text.startswith("طراد رفع اونر"):

        if not is_owner(user_id):
            return

        if not event.message.mention:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="منشن الشخص الاول")
            )
            return

        for m in event.message.mention.mentionees:
            owners.update_one(
                {"user": m.user_id},
                {"$set": {"user": m.user_id}},
                upsert=True
            )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم رفع اونر 🔥")
        )
        return


    if text.startswith("طراد تنزيل اونر"):

        if not is_owner(user_id):
            return

        if not event.message.mention:
            return

        for m in event.message.mention.mentionees:
            if m.user_id != OWNER_ID:
                owners.delete_one({"user": m.user_id})

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم تنزيل الاونر ✅")
        )
        return


    # ========= ADMIN =========

    if text.startswith("طراد رفع ادمن"):

        if not is_owner(user_id):
            return

        if not event.message.mention:
            return

        for m in event.message.mention.mentionees:
            admins.update_one(
                {"user": m.user_id},
                {"$set": {"user": m.user_id}},
                upsert=True
            )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم رفع ادمن ✅")
        )
        return


    if text.startswith("طراد تنزيل ادمن"):

        if not is_owner(user_id):
            return

        if not event.message.mention:
            return

        for m in event.message.mention.mentionees:
            admins.delete_one({"user": m.user_id})

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم تنزيل الادمن ✅")
        )
        return


    # ========= DELETE =========

    if text.startswith("طراد حذف"):

        trigger = text.replace("طراد حذف", "").strip()

        result = commands.delete_many({
            "group": group_id,
            "trigger": trigger
        })

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"تم حذف {result.deleted_count}")
        )
        return


    # ========= BAN =========

    if text.startswith("طراد حظر اسم"):

        if not is_admin(user_id):
            return

        name = text.replace("طراد حظر اسم", "").strip()

        banned_names.update_one(
            {"name": name},
            {"$set": {"name": name}},
            upsert=True
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم الحظر 🚫")
        )
        return


    # ================== HELP ==================
    
    if text == ".h":
    
        if not is_admin(user_id):
            return
    
        groups = commands.distinct("group")
    
        if not groups:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ مفيش أوامر متسجلة")
            )
            return
    
        # رد سريع علشان التوكن ميبقاش invalid
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📩 بعتلك الأوامر خاص")
        )
    
        for g in groups:
            try:
                summary = line_bot_api.get_group_summary(g)
                group_name = summary.group_name
            except:
                group_name = "جروب غير معروف"
    
            triggers = commands.distinct("trigger", {"group": g})
    
            if not triggers:
                continue
    
            msg = f"📌 {group_name}\n\n"
            msg += "\n".join([f"• {t}" for t in triggers])
    
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=msg))
            except:
                pass
    
        return


    # ========= REGISTER =========

    if text.startswith("طراد سجل"):

        trigger = text.replace("طراد سجل", "").strip()

        if banned(trigger):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="الاسم محظور")
            )
            return

        waiting[group_id] = {
            "trigger": trigger,
            "user": user_id
        }

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ابعت الرد 👍")
        )
        return


    # ========= SAVE TEXT =========

    if group_id in waiting:

        data = waiting[group_id]

        if data["user"] != user_id:
            return

        commands.insert_one({
            "group": group_id,
            "trigger": data["trigger"],
            "type": "text",
            "content": text
        })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="تم التسجيل ✅")
        )
        return


    # ========= AUTO REPLY =========
    results = list(commands.find({
        "group": group_id,
        "trigger": {"$regex": text, "$options": "i"}
    }))

    if not results:
        return

    data = random.choice(results)

    if data["type"] == "text":
        msg = TextSendMessage(text=data["content"])

    elif data["type"] == "sticker":
        msg = StickerSendMessage(
            package_id=data["package"],
            sticker_id=data["sticker"]
        )

    elif data["type"] == "image":
        msg = ImageSendMessage(
            original_content_url=data["url"],
            preview_image_url=data["url"]
        )

    else:
        msg = VideoSendMessage(
            original_content_url=data["url"],
            preview_image_url=data["url"]
        )

    line_bot_api.reply_message(event.reply_token, msg)


# ================= MEDIA =================

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, StickerMessage))
def handle_media(event):

    group_id = get_group_id(event)
    if not group_id:
        return

    user_id = event.source.user_id

    if group_id not in waiting:
        return

    data = waiting[group_id]

    if data["user"] != user_id:
        return

    trigger = data["trigger"]

    if isinstance(event.message, StickerMessage):

        commands.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": "sticker",
            "package": str(event.message.package_id),
            "sticker": str(event.message.sticker_id)
        })

    else:

        content = line_bot_api.get_message_content(event.message.id)
        file_path = f"/tmp/{event.message.id}"

        with open(file_path, "wb") as f:
            for chunk in content.iter_content():
                f.write(chunk)

        upload = cloudinary.uploader.upload(
            file_path,
            resource_type="auto"
        )

        file_type = "image" if isinstance(event.message, ImageMessage) else "video"

        commands.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": file_type,
            "url": upload["secure_url"]
        })

    del waiting[group_id]

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="تم تسجيل الرد ✅")
    )


# ================= RUN =================

if __name__ == "__main__":
    app.run()