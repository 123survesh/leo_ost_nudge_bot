import tweepy
import datetime
import os
import json
import random

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

BOT_ACCESS_TOKEN = os.environ.get("BOT_ACCESS_TOKEN")
BOT_ACCESS_TOKEN_SECRET = os.environ.get("BOT_ACCESS_TOKEN_SECRET")

# Authenticate with Twitter API v2
client = tweepy.Client(
    consumer_key=API_KEY, consumer_secret=API_SECRET,
    access_token=BOT_ACCESS_TOKEN, access_token_secret=BOT_ACCESS_TOKEN_SECRET
)

# Replace with the Tweet ID you want to reply to
target_tweet_id = "1847613033058570417"

def get_reminder_message():
    try:
        with open("reminder_messages.json", "r", encoding="utf-8") as f:
            messages = json.load(f)
            messages_count = len(messages)
            random_message_index = random.randint(0, messages_count-1)
            random_message = messages[random_message_index]
            return random_message["text"]
    except Exception as e:
        print(e)
        return  "@anirudhofficial bro, gentle reminder. [Sent at "
        

try:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = get_reminder_message()
    tweet_text = f"{message} {now}]"

    # Post the reply
    response = client.create_tweet(
        text=tweet_text,
        in_reply_to_tweet_id=target_tweet_id
    )
    print(f"Reply posted successfully: {response.data['id']}")
except Exception as e:
    print(f"Error: {e}")
