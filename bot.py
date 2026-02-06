from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

import os
import random
import re
import cloudinary
import cloudinary.uploader
from pymongo import MongoClient


app = Flask(__name__)

# ================= LINE =================
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# ================= MONGO =================
mongo = MongoClient(os.getenv("MONGO"))
db = mongo["protect_bot"]

commands = db.commands
owners = db.owners
admins = db.admins
blocked = db.blocked_words

blocked.create_index("word", unique=True)

# ================= CLOUDINARY =================
cloudinary.config(secure=True)

waiting = {}

# ================= SMART NORMALIZE =================

def normalize(text):
    text = text.lower()

    # حذف المسافات
    text = text.replace(" ", "")

    # حذف التكرار
    text = re.sub(r'(.)\1+', r'\1', text)

    # تحويل عربي / إنجليزي قريب
    replace_map = {
        "4": "a",
        "@": "a",
        "0": "o",
        "1": "i",
        "3": "e",
        "7": "h",
        "9": "q"
    }

    for k,v in replace_map.items():
        text = text.replace(k, v)

    return text


# ================= PERMISSIONS =================

def is_owner(uid):
    return owners.find_one({"user_id": uid}) is not None


def is_admin(uid):
    return admins.find_one({"user_id": uid}) is not None


def is_admin_or_owner(uid):
    return is_owner(uid) or is_admin(uid)


# ================= BLOCK CHECK =================

def is_blocked(word):

    normalized = normalize(word)

    for w in blocked.find():
        if normalize(w["word"]) in normalized or normalized in normalize(w["word"]):
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


# ================= MESSAGE =================

@handler.add(MessageEvent)
def handle_message(event):

    if not hasattr(event.source, "group_id"):
        return

    group_id = event.source.group_id
    user_id = event.source.user_id


    # ================= TEXT =================
    if isinstance(event.message, TextMessage):

        text = event.message.text.strip()


        # ===== رفع اونر =====
        if text.startswith("طراد رفع اونر"):

            if not is_owner(user_id):
                return

            if event.message.mention:

                for m in event.message.mention.mentionees:
                    owners.update_one(
                        {"user_id": m.user_id},
                        {"$set": {"user_id": m.user_id}},
                        upsert=True
                    )

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="👑 تم رفعه اونر")
                )
            return


        # ===== رفع ادمن =====
        if text.startswith("طراد رفع ادمن"):

            if not is_owner(user_id):
                return

            if event.message.mention:

                for m in event.message.mention.mentionees:
                    admins.update_one(
                        {"user_id": m.user_id},
                        {"$set": {"user_id": m.user_id}},
                        upsert=True
                    )

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="🔥 تم رفعه ادمن")
                )
            return


        # ===== حظر كلمة =====
        if text.startswith("طراد حظر اسم"):

            if not is_admin_or_owner(user_id):
                return

            word = text.replace("طراد حظر اسم","").strip()

            if not word:
                return

            blocked.update_one(
                {"word": word},
                {"$set":{"word": word}},
                upsert=True
            )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"🚫 تم حظر ({word}) في كل الجروبات")
            )
            return


        # ===== فك الحظر =====
        if text.startswith("طراد فك حظر"):

            if not is_admin_or_owner(user_id):
                return

            word = text.replace("طراد فك حظر","").strip()

            blocked.delete_one({"word": word})

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ تم فك الحظر عن ({word})")
            )
            return


        # ===== تسجيل امر =====
        if text.startswith("طراد سجل"):


            trigger = text.replace("طراد سجل","").strip()

            if is_blocked(trigger):

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="❌ الاسم دا محظور عالمياً")
                )
                return


            waiting[group_id] = {
                "trigger": trigger,
                "owner": user_id
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🔥 ابعت الرد دلوقتي")
            )
            return
        
         # ===== اظهار الاوامر لكل جروب =====
if text == ".h":

    if not is_admin_or_owner(user_id):
        return

    groups = commands.distinct("group")

    if not groups:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ مفيش اوامر متسجلة")
        )
        return


    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🔥 ببعتلك الاوامر برايفت...")
    )

    for g in groups:

        triggers = commands.distinct("trigger", {"group": g})

        msg = "📌 اوامر جروب:\n\n"

        for t in triggers:
            msg += f"• {t}\n"

        if len(msg) > 4900:
            msg = msg[:4900]


        line_bot_api.push_message(
            event.source.user_id,  # يبعته لك برايفت
            TextSendMessage(text=msg)
        )


        # ===== حذف امر =====
        if text.startswith("طراد حذف"):



            trigger = text.replace("طراد حذف","").strip()

            commands.delete_many({
                "group": group_id,
                "trigger": trigger
            })

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ تم حذف الامر")
            )
            return


        # ===== الرد =====
        results = list(commands.find({
            "group": group_id,
            "trigger": text
        }))

        if results:

            data = random.choice(results)

            t = data["type"]

            if t == "text":
                msg = TextSendMessage(text=data["content"])

            elif t == "sticker":
                msg = StickerSendMessage(
                    package_id=str(data["package"]),
                    sticker_id=str(data["sticker"])
                )

            elif t == "image":
                msg = ImageSendMessage(
                    original_content_url=data["url"],
                    preview_image_url=data["url"]
                )

            elif t == "video":
                msg = VideoSendMessage(
                    original_content_url=data["url"],
                    preview_image_url=data["url"]
                )

            else:
                return

            line_bot_api.reply_message(event.reply_token, msg)
            return


    # ================= SAVE =================

    if group_id not in waiting:
        return

    if waiting[group_id]["owner"] != user_id:
        return

    trigger = waiting[group_id]["trigger"]


    # نص
    if isinstance(event.message, TextMessage):

        commands.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": "text",
            "content": event.message.text
        })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ تم تسجيل النص")
        )
        return


    # استيكر
    if isinstance(event.message, StickerMessage):

        commands.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": "sticker",
            "package": event.message.package_id,
            "sticker": event.message.sticker_id
        })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔥 تم تسجيل الاستيكر")
        )
        return


    # ميديا
    content = line_bot_api.get_message_content(event.message.id)

    file_path = f"/tmp/{event.message.id}"

    with open(file_path, "wb") as f:
        for chunk in content.iter_content():
            f.write(chunk)

    upload = cloudinary.uploader.upload(file_path, resource_type="auto")

    media_type = "image"

    if isinstance(event.message, VideoMessage):
        media_type = "video"

    commands.insert_one({
        "group": group_id,
        "trigger": trigger,
        "type": media_type,
        "url": upload["secure_url"]
    })

    del waiting[group_id]

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🚀 تم تسجيل الميديا")
    )


if __name__ == "__main__":
    app.run()