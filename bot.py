from flask import Flask, request, abort
import os, json, random, time

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# ================== CONFIG ==================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError("❌ Missing LINE credentials in Environment Variables!")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)

# ================== LOAD FILES ==================

def load_json(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

questions_data = load_json("questions.json")
words_data = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")

# ================== NO REPEAT SYSTEM ==================

def create_queue(data):
    q = data.copy()
    random.shuffle(q)
    return q

questions_queue = create_queue(questions_data)
words_queue = create_queue(words_data)
race_queue = create_queue(race_data)
tf_queue = create_queue(tf_data)

# ================== STORAGE ==================

points = {}
user_cache = {}
last_message = {}

# ================== GAME STATE ==================

current_answer = None
current_word = None
race_text = None
tf_answer = None

# ================== HELPERS ==================

def scramble(word):
    mixed = word
    while mixed == word:
        mixed = ''.join(random.sample(word, len(word)))
    return mixed

def anti_spam(user_id):
    now = time.time()
    if user_id in last_message:
        if now - last_message[user_id] < 1:
            return True
    last_message[user_id] = now
    return False

def add_points(user, amount=2):
    points[user] = points.get(user, 0) + amount


# ================== WEBHOOK ==================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("CRASH:", e)

    return 'OK'


@app.route("/")
def home():
    return "🔥 BOT RUNNING"


# ================== MESSAGE ==================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    global current_answer, current_word, race_text, tf_answer
    global questions_queue, words_queue, race_queue, tf_queue

    try:

        user_id = event.source.user_id
        msg = event.message.text.strip().lower()

        if anti_spam(user_id):
            return

        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)

            username = user_cache.get(user_id, "Player")
            user_cache[user_id] = username

            reply = None

            # ================= MENU =================

            if msg in ["اوامر", "menu"]:
                reply = """
🔥 GAME BOT 🔥

🧠 سؤال
⚡ مين الأسرع
🏁 سباق
✔️ صح ولا غلط
🏆 نقاطي
🥇 توب
"""

            # ================= QUESTIONS =================

            elif msg == "سؤال":

                if not questions_queue:
                    questions_queue = create_queue(questions_data)

                q = questions_queue.pop()

                current_answer = q["a"].lower()

                reply = f"🧠 {q['q']}"

            elif current_answer and current_answer in msg:

                add_points(user_id)
                reply = "🔥 إجابة صحيحة!"

                current_answer = None

            # ================= FAST WORD =================

            elif msg == "مين الأسرع":

                if not words_queue:
                    words_queue = create_queue(words_data)

                word = words_queue.pop()
                current_word = word

                reply = f"⚡ رتب الكلمة:\n🔥 {scramble(word)}"

            elif current_word and msg == current_word:

                add_points(user_id)
                reply = "🚀 أسرع لاعب!"

                current_word = None

            # ================= RACE =================

            elif msg == "سباق":

                if not race_queue:
                    race_queue = create_queue(race_data)

                race_text = race_queue.pop().lower()

                reply = f"🏁 اكتب:\n{race_text}"

            elif race_text and msg == race_text:

                add_points(user_id)
                reply = "🔥 فاز بالسباق!"

                race_text = None

            # ================= TRUE/FALSE =================

            elif msg == "صح ولا غلط":

                if not tf_queue:
                    tf_queue = create_queue(tf_data)

                q = tf_queue.pop()

                tf_answer = q["a"].lower()

                reply = f"🧠 {q['q']}"

            elif tf_answer and msg == tf_answer:

                add_points(user_id)
                reply = "✔️ إجابة صح!"

                tf_answer = None

            # ================= POINTS =================

            elif msg == "نقاطي":
                reply = f"🏆 معاك {points.get(user_id,0)} نقطة"

            elif msg == "توب":

                if not points:
                    reply = "لسه محدش لعب 😄"
                else:
                    top = sorted(points.items(),
                                 key=lambda x: x[1],
                                 reverse=True)[:10]

                    text = "🥇 أقوى اللاعبين:\n"

                    for i, (u, s) in enumerate(top, start=1):
                        text += f"{i}- {user_cache.get(u,'Player')} ({s})\n"

                    reply = text

            # ================= SEND =================

            if reply:
                api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )

    except Exception as e:
        print("BOT ERROR:", e)