import os
import random
import cloudinary
import cloudinary.uploader

from flask import Flask, request, abort
from pymongo import MongoClient

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

# ================== CONFIG ==================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
CLOUD_NAME = os.getenv("CLOUD_NAME")
CLOUD_KEY = os.getenv("CLOUD_KEY")
CLOUD_SECRET = os.getenv("CLOUD_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

client = MongoClient(MONGO_URI)
db = client["linebot"]

commands = db["commands"]
admins = db["admins"]
owners = db["owners"]
banned_names = db["banned"]

OWNER_ID = os.getenv("OWNER_ID")

if OWNER_ID and not owners.find_one({"user": OWNER_ID}):
    owners.insert_one({"user": OWNER_ID})


cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=CLOUD_KEY,
    api_secret=CLOUD_SECRET
)

app = Flask(__name__)

waiting = {}  # تخزين اللي بيعمل تسجيل مؤقت

# ================== HELPERS ==================

def get_group_id(event):
    if event.source.type == "group":
        return event.source.group_id
    elif event.source.type == "room":
        return event.source.room_id
    return event.source.user_id


def is_owner(user):
    return owners.find_one({"user": user})


def is_admin(user):
    return admins.find_one({"user": user}) or is_owner(user)


def name_banned(trigger):
    banned = banned_names.find()

    for b in banned:
        word = b["name"]

        # يمنع التكرار زي قطااام
        if word in trigger:
            return True

    return False


# ================== WEBHOOK ==================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================== MESSAGE ==================

@handler.add(MessageEvent)
def handle_message(event):

    if not isinstance(event.message, Message):
        return

    group_id = get_group_id(event)
    user_id = event.source.user_id

    # نخلي التسجيل في الجروبات بس
    if event.source.type == "user":
        return

    # ================== TEXT ==================

    if isinstance(event.message, TextMessage):

        text = event.message.text.strip()

        # ================== OWNER ==================

        if text.startswith("طراد رفع اونر"):

            if not is_owner(user_id):
                return

            for m in event.message.mentions.mentionees:
                owners.update_one(
                    {"user": m.user_id},
                    {"$set": {"user": m.user_id}},
                    upsert=True
                )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم رفع اونر")
            )
            return
            
        # ================== DELETE ==================

        if text.startswith("طراد حذف"):
        
            trigger = text.replace("طراد حذف", "").strip()
        
            if not trigger:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="❌ اكتب اسم الامر اللي عايز تحذفه")
                )
                return
        
            result = commands.delete_many({
                "group": group_id,
                "trigger": trigger
            })
        
            if result.deleted_count == 0:
                msg = "❌ الامر مش موجود"
            else:
                msg = f"✅ تم حذف {result.deleted_count} رد"
        
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
        
            return
    
    
        
        # ================== ADMIN ==================

        if text.startswith("طراد رفع ادمن"):

            if not is_owner(user_id):
                return

            for m in event.message.mentions.mentionees:
                admins.update_one(
                    {"user": m.user_id},
                    {"$set": {"user": m.user_id}},
                    upsert=True
                )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم رفع ادمن")
            )
            return

        # ================== BAN NAME ==================

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
                TextSendMessage(text=f"🚫 تم حظر الاسم: {name}")
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

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="📩 بص الخاص")
            )

            for g in groups:
                try:
                   group_summary = line_bot_api.get_group_summary(g)
                   group_name = group_summary.group_name
                except:
                    group_name = "جروب غير معروف"
                    
                triggers = commands.distinct("trigger", {"group": g})

                msg = f"📌 اسم الجروب: {group_name}\n\n"
                msg += "\n".join(triggers)

                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text=msg)
                )

            return

        # ================== REGISTER ==================

        if text.startswith("طراد سجل"):

            trigger = text.replace("طراد سجل", "").strip()

            if not trigger:
                return

            if name_banned(trigger):
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="🚫 الاسم محظور")
                )
                return

            waiting[group_id] = {
                "trigger": trigger,
                "user": user_id
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🔥 ابعت الرد (نص / صورة / فيديو / استيكر)")
            )
            return

        # ================== SAVE TEXT ==================

        if group_id in waiting:

            data_wait = waiting[group_id]

            if data_wait["user"] != user_id:
                return

            commands.insert_one({
                "group": group_id,
                "trigger": data_wait["trigger"],
                "type": "text",
                "content": text
            })

            del waiting[group_id]

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم التسجيل")
            )
            return

        # ================== AUTO REPLY ==================

        results = list(commands.find({
            "group": group_id,
            "trigger": text
        }))

        if not results:
            return

        data = random.choice(results)

        t = data["type"]

        if t == "text":
            msg = TextSendMessage(text=data["content"])

        elif t == "sticker":
            msg = StickerSendMessage(
                package_id=data["package"],
                sticker_id=data["sticker"]
            )

        else:
            msg = ImageSendMessage(
                original_content_url=data["url"],
                preview_image_url=data["url"]
            )

        line_bot_api.reply_message(event.reply_token, msg)
        return


    # ================== MEDIA ==================

    if group_id in waiting:

        data_wait = waiting[group_id]

        if data_wait["user"] != user_id:
            return

        trigger = data_wait["trigger"]

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

            commands.insert_one({
                "group": group_id,
                "trigger": trigger,
                "type": "media",
                "url": upload["secure_url"]
            })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ تم تسجيل الرد")
        )


# ================== RUN ==================

if __name__ == "__main__":
    app.run()