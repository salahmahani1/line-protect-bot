import os
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

from pymongo import MongoClient


# ====== ENV ======
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
MONGO_URL = os.getenv("MONGO_URL")

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

client = MongoClient(MONGO_URL)
db = client["trigger_bot"]
collection = db["triggers"]

app = Flask(__name__)

waiting_trigger = {}  # الجروبات اللي مستنية ميديا


# ====== Webhook ======
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ====== Messages ======
@handler.add(MessageEvent)
def handle_message(event):

    group_id = getattr(event.source, "group_id", None)

    if group_id is None:
        group_id = event.source.user_id  # لو برايفت

    # ========= TEXT =========
    if isinstance(event.message, TextMessage):

        text = event.message.text.strip().lower()

        # تسجيل امر
        if text.startswith("طراد سجل"):

            trigger = text.replace("طراد سجل", "").strip()

            if not trigger:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="قول الكلمة بعد الامر 😄")
                )
                return

            waiting_trigger[group_id] = trigger

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"🔥 ابعت صورة او فيديو او استيكر علشان اربطها بـ ({trigger})"
                )
            )
            return

        # حذف امر
        if text.startswith("طراد حذف"):

            trigger = text.replace("طراد حذف", "").strip()

            collection.delete_one({
                "group": group_id,
                "trigger": trigger
            })

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ اتمسح الامر")
            )
            return

        # عرض الاوامر
        if text == "طراد الاوامر":

            data = collection.find({"group": group_id})

            triggers = [d["trigger"] for d in data]

            if not triggers:
                msg = "مفيش اوامر متسجلة 😅"
            else:
                msg = "🔥 الاوامر:\n\n" + "\n".join(triggers[:50])

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return

        # الرد على التريجر
        data = collection.find_one({
            "group": group_id,
            "trigger": text
        })

        if data:

            if data["type"] == "image":
                msg = ImageSendMessage(
                    original_content_url=data["url"],
                    preview_image_url=data["url"]
                )

            elif data["type"] == "video":
                msg = VideoSendMessage(
                    original_content_url=data["url"],
                    preview_image_url=data["preview"]
                )

            elif data["type"] == "sticker":
                msg = StickerSendMessage(
                    package_id=data["package"],
                    sticker_id=data["sticker"]
                )

            line_bot_api.reply_message(event.reply_token, msg)
            return

    # ========= MEDIA =========
    if group_id in waiting_trigger:

        trigger = waiting_trigger[group_id]

        # استيكر
        if isinstance(event.message, StickerMessage):

            collection.insert_one({
                "group": group_id,
                "trigger": trigger,
                "type": "sticker",
                "package": event.message.package_id,
                "sticker": event.message.sticker_id
            })

        # صورة او فيديو
        elif isinstance(event.message, (ImageMessage, VideoMessage)):

            content = line_bot_api.get_message_content(event.message.id)

            file_path = f"{event.message.id}.dat"

            with open(file_path, "wb") as f:
                for chunk in content.iter_content():
                    f.write(chunk)

            # ⚠️ ارفع الملف على Cloudinary او اي Storage
            url = "PUT_FILE_URL_HERE"

            collection.insert_one({
                "group": group_id,
                "trigger": trigger,
                "type": "image",
                "url": url,
                "preview": url
            })

        del waiting_trigger[group_id]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"✅ اتسجل ({trigger}) بنجاح 🔥")
        )


# ====== RUN ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)