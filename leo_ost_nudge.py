import tweepy
import datetime
import os

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

try:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tweet_text = f"@anirudhofficial bro, gentle reminder. [Sent at {now}]"
    # Post the reply
    response = client.create_tweet(
        text=tweet_text,
        in_reply_to_tweet_id=target_tweet_id
    )
    print(f"Reply posted successfully: {response.data['id']}")
except Exception as e:
    print(f"Error: {e}")
