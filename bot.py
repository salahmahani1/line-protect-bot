from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

import google.generativeai as genai

import os
import json
import random
import time

# ================= CONFIG =================

CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

GEMINI_API_KEY = "AIzaSyBRLGECNo6M4Y-1B-uWcovx-Leh_aC2mos"

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-pro")

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
ai_groups = load_json("ai_groups.json", {"groups": []})

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================= DATA =================

admins = load_json("admins.json", [])
economy = load_json("economy.json", {})
mentions = load_json("mentions.json", {"waiting": {}})

# ================= AI =================

def ai_reply(message):
    try:
        response = model.generate_content(
            f"""
انت شاب مصري هزار ودمك خفيف.
ردودك قصيرة.
بتفهم الهزار.
ممنوع تقول انك AI.

الرسالة:
{message}
"""
        )

        return response.text

    except Exception as e:
        print("AI ERROR:", e)
        return "حاسس ان مخي فصل ثانية 😂"
# ================= ROUTE =================

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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        msg = event.message.text.lower()
        user_id = event.source.user_id

        reply = None
        group_id = None
        
        if event.source.type == "group":
            group_id = event.source.group_id
            AI_ON = group_id in ai_groups["groups"]
        # ================= ADMIN =================
        

        if msg == "رفعني":
            if user_id not in admins:
                admins.append(user_id)
                save_json("admins.json", admins)
                reply = "بقيت ادمن اهو 😎"

        if msg == "الادمن":
            reply = f"عدد الادمنز: {len(admins)}"
            
        if msg == "تشغيل ai" and user_id in admins:

    if group_id not in ai_groups["groups"]:
        ai_groups["groups"].append(group_id)
        save_json("ai_groups.json", ai_groups)
        reply = "تم تشغيل الذكاء الاصطناعي هنا 🧠🔥"

    else:
        reply = "هو شغال بالفعل 😏"
        
        if msg == "ايقاف ai" and user_id in admins:

    if group_id in ai_groups["groups"]:
        ai_groups["groups"].remove(group_id)
        save_json("ai_groups.json", ai_groups)
        reply = "تم إيقاف الذكاء 😴"

    else:
        reply = "هو أصلا مقفول 😂"

        # ================= ECONOMY =================

        if msg == "فلوسي":
            coins = economy.get(user_id, 0)
            reply = f"معاك {coins} كوين 💰"

        if msg == "راتب":
            last = economy.get(f"time_{user_id}", 0)

            if time.time() - last > 86400:
                economy[user_id] = economy.get(user_id, 0) + 100
                economy[f"time_{user_id}"] = time.time()

                save_json("economy.json", economy)

                reply = "قبضت 100 كوين 💸"
            else:
                reply = "استنى بكرة 😏"

        # ================= SMART MENTION =================

        if event.message.mention:
            try:
                target = event.message.mention.mentionees[0].user_id
                mentions["waiting"][target] = True
                save_json("mentions.json", mentions)

                reply = "هبلغه لما يرجع 😉"
            except:
                pass

        if user_id in mentions.get("waiting", {}):
            del mentions["waiting"][user_id]
            save_json("mentions.json", mentions)

            reply = random.choice([
                "نورت يا غايب 👀",
                "تعالى هنا كنت بتستخبى فين 😏",
                "الناس كانت بتدور عليك 😂"
            ])

        # ================= AI =================

        trigger_words = ["بوت", "يا بوت", "@"]

        if not reply and AI_ON and any(word in msg for word in trigger_words):
            reply = ai_reply(msg)
        # fallback
        if not reply:
            return

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)