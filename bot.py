import os
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

from pymongo import MongoClient

import cloudinary
import cloudinary.uploader


# ================= CONFIG =================

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

client = MongoClient(os.getenv("MONGO_URL"))
db = client["trigger_bot"]
collection = db["triggers"]

cloudinary.config(secure=True)

app = Flask(__name__)

waiting = {}  # الجروب مستني ايه


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


# ================= BOT =================

@handler.add(MessageEvent)
def handle_message(event):

    group_id = getattr(event.source, "group_id", None)

    if group_id is None:
        group_id = event.source.user_id

    # ================= TEXT =================

    if isinstance(event.message, TextMessage):

        text = event.message.text.strip()

        # تسجيل
        if text.startswith("طراد سجل"):

            trigger = text.replace("طراد سجل", "").strip().lower()

            if not trigger:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="اكتب اسم الامر بعد (طراد سجل)")
                )
                return

            waiting[group_id] = trigger

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"🔥 ابعت نص او صورة او فيديو علشان اربطها بـ ({trigger})"
                )
            )
            return

        # حذف
        if text.startswith("طراد حذف"):

            trigger = text.replace("طراد حذف", "").strip().lower()

            collection.delete_one({
                "group": group_id,
                "trigger": trigger
            })

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ اتمسح الامر")
            )
            return

        # عرض
        if text == "طراد الاوامر":

            data = collection.find({"group": group_id})

            triggers = [d["trigger"] for d in data]

            msg = "🔥 الاوامر:\n\n" + "\n".join(triggers[:50]) if triggers else "مفيش اوامر"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return

        # الرد
        data = collection.find_one({
            "group": group_id,
            "trigger": text.lower()
        })

        if data:

            t = data["type"]

            if t == "text":
                msg = TextSendMessage(text=data["content"])

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

            elif t == "sticker":
                msg = StickerSendMessage(
                    package_id=data["package"],
                    sticker_id=data["sticker"]
                )

            line_bot_api.reply_message(event.reply_token, msg)
            return

        # لو مستني نص يتسجل
        if group_id in waiting:

            trigger = waiting[group_id]

            collection.insert_one({
                "group": group_id,
                "trigger": trigger,
                "type": "text",
                "content": text
            })

            del waiting[group_id]

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ اتسجل ({trigger})")
            )
            return

    # ================= MEDIA =================

    if group_id in waiting:

        trigger = waiting[group_id]

        # استيكر
        if isinstance(event.message, StickerMessage):

            collection.insert_one({
                "group": group_id,
                "trigger": trigger,
                "type": "sticker",
                "package": event.message.package_id,
                "sticker": event.message.sticker_id
            })

        else:
            # تحميل الملف من LINE
            content = line_bot_api.get_message_content(event.message.id)

            file_path = f"{event.message.id}.dat"

            with open(file_path, "wb") as f:
                for chunk in content.iter_content():
                    f.write(chunk)

            # رفع Cloudinary
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
            TextSendMessage(text=f"🔥 اتسجل ({trigger}) بنجاح")
        )


# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)