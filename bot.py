

from flask import Flask, request, abort
import json, random, time

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

# 🔥 حط التوكن هنا
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= LOAD FILES =================

def load_json(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

questions_data = load_json("questions.json")
words_data = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")

def create_queue(data):
    q = data.copy()
    random.shuffle(q)
    return q

questions_queue = create_queue(questions_data)
words_queue = create_queue(words_data)
race_queue = create_queue(race_data)
tf_queue = create_queue(tf_data)

# ================= STORAGE =================

points = {}
last_message = {}

current_answer = None
current_word = None
current_race = None
tf_answer = None

# ================= HELPERS =================

def normalize(text):
    return text.replace(" ", "").lower()

def anti_spam(user_id):
    now = time.time()
    if user_id in last_message:
        if now - last_message[user_id] < 1:
            return True
    last_message[user_id] = now
    return False

def add_points(user, amount=1):
    points[user] = points.get(user, 0) + amount

def scramble(word):
    mixed = word
    while mixed == word:
        mixed = ''.join(random.sample(word, len(word)))
    return mixed

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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    global current_answer, current_word, current_race, tf_answer
    global questions_queue, words_queue, race_queue, tf_queue

    user_id = event.source.user_id
    msg = event.message.text.strip().lower()

    if anti_spam(user_id):
        return

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        reply = None

        # ================= MENU =================

        if msg in ["العاب", "menu", "help"]:
            reply = """
🔥 الألعاب المتاحة:

🧠 سوال → سؤال وجواب  
⚡ مين الاسرع → اكتب الجملة بسرعة  
🔤 رتب → رتب الكلمة  
✅ صح غلط → صح ولا غلط  
🏆 توب → أقوى اللاعبين  

اكتب اسم اللعبة بس 😈
"""

        # ================= QUESTIONS =================

        elif msg == "سوال":
            if not questions_queue:
                questions_queue = create_queue(questions_data)

            q = questions_queue.pop()
            current_answer = normalize(q["a"])

            reply = f"🧠 {q['q']}"

        elif current_answer and normalize(msg) == current_answer:
            add_points(user_id, 2)
            reply = "🔥 إجابة صحيحة +2 نقاط!"
            current_answer = None

        # ================= TRUE FALSE =================

        elif msg in ["صح غلط", "صح ولا غلط"]:
            if not tf_queue:
                tf_queue = create_queue(tf_data)

            q = tf_queue.pop()
            tf_answer = normalize(q["a"])

            reply = f"✅ صح أم غلط:\n{q['q']}"

        elif tf_answer and normalize(msg) == tf_answer:
            add_points(user_id, 1)
            reply = "👏 صح +1 نقطة!"
            tf_answer = None

        # ================= SCRAMBLE =================

        elif msg == "رتب":
            if not words_queue:
                words_queue = create_queue(words_data)

            word = words_queue.pop()
            current_word = normalize(word)

            reply = f"🔤 رتب الكلمة:\n{scramble(word)}"

        elif current_word and normalize(msg) == current_word:
            add_points(user_id, 2)
            reply = "🔥 برافو رتبتها صح +2 نقاط!"
            current_word = None

        # ================= RACE =================

        elif msg == "مين الاسرع":
            if not race_queue:
                race_queue = create_queue(race_data)

            current_race = race_queue.pop()
            reply = f"⚡ اكتب بسرعة:\n{current_race}"

        elif current_race and normalize(msg) == normalize(current_race):
            add_points(user_id, 3)
            reply = "🚀 انت الأسرع! +3 نقاط"
            current_race = None

        # ================= TOP =================

        elif msg == "توب":
            if not points:
                reply = "لسه محدش لعب 😄"
            else:
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:10]

                text = "🏆 أقوى اللاعبين:\n\n"
                for i,(u,s) in enumerate(top,1):
                    text += f"{i}- لاعب ({s}) نقطة\n"

                reply = text

        # ================= SEND =================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )

# ================= SERVER =================

@app.route("/", methods=["GET"])
def home():
    return "BOT IS RUNNING 🔥"

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)