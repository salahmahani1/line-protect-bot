from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import random
import cloudinary
import cloudinary.uploader
from pymongo import MongoClient

app = Flask(__name__)

# ===== LINE =====
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# ===== MongoDB =====
mongo = MongoClient(os.getenv("MONGO"))
db = mongo["linebot"]
collection = db["commands"]

# ===== Cloudinary =====
cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("CLOUD_KEY"),
    api_secret=os.getenv("CLOUD_SECRET")
)

# تخزين مؤقت للي بيعمل تسجيل
waiting = {}


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent)
def handle_message(event):

    if not hasattr(event.source, "group_id"):
        return

    group_id = event.source.group_id
    user_id = event.source.user_id

    # =========================
    # TEXT
    # =========================
    if isinstance(event.message, TextMessage):

        text = event.message.text.strip()

        # -------- تسجيل --------
        if text.startswith("طراد سجل"):

            trigger = text.replace("طراد سجل", "").strip()

            if not trigger:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="اكتب الكلمة بعد (طراد سجل)")
                )
                return

            waiting[group_id] = {
                "trigger": trigger,
                "owner": user_id
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"🔥 ابعت نص او صورة او فيديو علشان اربطه بـ ({trigger})"
                )
            )
            return

        # -------- حذف --------
        if text.startswith("طراد حذف"):

            trigger = text.replace("طراد حذف", "").strip()

            collection.delete_many({
                "group": group_id,
                "trigger": trigger
            })

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ اتمسح الامر")
            )
            return

        # ================= الرد العشوائي =================

        results = list(collection.find({
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

        elif t == "file":
            msg = FileSendMessage(
                original_content_url=data["url"],
                file_name="file"
            )

        else:
            return

        line_bot_api.reply_message(event.reply_token, msg)
        return


    # =========================
    # لو في تسجيل شغال
    # =========================

    if group_id not in waiting:
        return

    if waiting[group_id]["owner"] != user_id:
        return

    trigger = waiting[group_id]["trigger"]

    # -------- نص --------
    if isinstance(event.message, TextMessage):

        collection.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": "text",
            "content": event.message.text
        })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ اتسجل الرد")
        )
        return


    # -------- استيكر --------
    if isinstance(event.message, StickerMessage):

        collection.insert_one({
            "group": group_id,
            "trigger": trigger,
            "type": "sticker",
            "package": event.message.package_id,
            "sticker": event.message.sticker_id
        })

        del waiting[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔥 اتسجل الاستيكر")
        )
        return


    # ================= MEDIA =================

    message_id = event.message.id
    content = line_bot_api.get_message_content(message_id)

    file_path = f"/tmp/{message_id}"

    with open(file_path, "wb") as f:
        for chunk in content.iter_content():
            f.write(chunk)

    upload = cloudinary.uploader.upload(
        file_path,
        resource_type="auto"
    )

    url = upload["secure_url"]

    media_type = "file"

    if isinstance(event.message, ImageMessage):
        media_type = "image"

    elif isinstance(event.message, VideoMessage):
        media_type = "video"

    collection.insert_one({
        "group": group_id,
        "trigger": trigger,
        "type": media_type,
        "url": url
    })

    del waiting[group_id]

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🚀 اتسجل الميديا")
    )


if __name__ == "__main__":
    app.run()