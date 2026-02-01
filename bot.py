from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_id = event.source.user_id

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"Your ID: {user_id}")
    )


if __name__ == "__main__":
    app.run(port=5000)

