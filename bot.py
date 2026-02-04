from flask import Flask, request, abort
import json
import os
import time
import random
from collections import defaultdict

from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# ================= CONFIG =================

CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# قائمة المالكين (أصحاب البوت)
OWNERS = [
    "U9ecd575f8df0e62798f4c8ecc9738d5d",
    "U3617621ee527f90ad2ee0231c8bf973f",
]


app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ================= SAFE JSON =================

def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(file, data):
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, file)


admins = list(set(load_json("admins.json", []) + OWNERS))
save_json("admins.json", admins)

points = load_json("points.json", {})
economy = load_json("economy.json", {})
mentions = load_json("mentions.json", {"waiting": {}})


# ================= ANTI SPAM =================

cooldowns = defaultdict(float)

def spam_block(user):
    now = time.time()
    if now - cooldowns[user] < 1:
        return True
    cooldowns[user] = now
    return False


# ================= SERVER =================

@app.route("/")
def home():
    return "BOT ALIVE"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================= MESSAGE HANDLER =================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    msg = event.message.text.strip()

    if spam_block(user_id):
        return

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        try:
            name = api.get_profile(user_id).display_name
        except:
            name = "لاعب"

        reply = None

        try:

            # ================= OWNERS / ADMINS =================

            if msg == "الادمن":
                reply = f"عدد الادمنز: {len(admins)}"

            if msg.startswith("رفع") and user_id in OWNERS:
                if event.message.mention:
                    target = event.message.mention.mentionees[0].user_id
                    if target not in admins:
                        admins.append(target)
                        save_json("admins.json", admins)
                        reply = "✅ تم رفعه ادمن"

            if msg.startswith("تنزيل") and user_id in OWNERS:
                if event.message.mention:
                    target = event.message.mention.mentionees[0].user_id
                    if target in admins:
                        admins.remove(target)
                        save_json("admins.json", admins)
                        reply = "✅ تم تنزيل الادمن"

            # ================= ECONOMY =================

            if msg == "راتب":
                last = economy.get(user_id, 0)

                if time.time() - last > 86400:
                    points[user_id] = points.get(user_id, 0) + 500
                    economy[user_id] = time.time()

                    save_json("points.json", points)
                    save_json("economy.json", economy)

                    reply = "💰 اخدت 500 نقطة"
                else:
                    reply = "استنى بكرة 😄"

            if msg == "فلوسي":
                reply = f"معاك {points.get(user_id,0)} نقطة"

            # ================= SMART MENTION =================

            if event.message.mention:

                target = event.message.mention.mentionees[0].user_id
                mentions["waiting"][target] = True
                save_json("mentions.json", mentions)

                reply = "هبلغه لما يرجع 😏"

            if user_id in mentions["waiting"]:
                del mentions["waiting"][user_id]
                save_json("mentions.json", mentions)

                reply = random.choice([
                    "👀 حد كان بيدور عليك",
                    "تعالى يا نجم كانوا بيسألوا عليك 😂",
                    "صح النوم 😏"
                ])

        except Exception as e:
            print("CRASH BLOCKED:", e)


        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)