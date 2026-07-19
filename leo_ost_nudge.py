import datetime
import json
import os
import random
import urllib.error
import urllib.request

import tweepy

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

BOT_ACCESS_TOKEN = os.environ.get("BOT_ACCESS_TOKEN")
BOT_ACCESS_TOKEN_SECRET = os.environ.get("BOT_ACCESS_TOKEN_SECRET")

TWITTER_BACKEND = os.environ.get("TWITTER_BACKEND", "twitter").lower()
XQUIK_API_KEY = os.environ.get("XQUIK_API_KEY")
XQUIK_ACCOUNT = os.environ.get("XQUIK_ACCOUNT")
XQUIK_API_BASE = os.environ.get("XQUIK_API_BASE", "https://xquik.com/api/v1")

# Replace with the Tweet ID you want to reply to
target_tweet_id = "1847613033058570417"


def get_reminder_message():
    try:
        with open("reminder_messages.json", "r", encoding="utf-8") as f:
            messages = json.load(f)
            messages_count = len(messages)
            random_message_index = random.randint(0, messages_count - 1)
            random_message = messages[random_message_index]
            return random_message
    except Exception as e:
        print(e)
        return {
            "text": "@anirudhofficial bro, gentle reminder. [Sent at ",
            "language": "English",
        }


def require_env(name, value):
    if not value:
        raise ValueError(f"{name} is required")
    return value


def post_with_twitter(tweet_text):
    client = tweepy.Client(
        consumer_key=require_env("API_KEY", API_KEY),
        consumer_secret=require_env("API_SECRET", API_SECRET),
        access_token=require_env("BOT_ACCESS_TOKEN", BOT_ACCESS_TOKEN),
        access_token_secret=require_env(
            "BOT_ACCESS_TOKEN_SECRET", BOT_ACCESS_TOKEN_SECRET
        ),
    )
    response = client.create_tweet(
        text=tweet_text,
        in_reply_to_tweet_id=target_tweet_id,
    )
    return response.data["id"]


def post_with_xquik(tweet_text):
    api_key = require_env("XQUIK_API_KEY", XQUIK_API_KEY)
    payload = json.dumps(
        {
            "account": require_env("XQUIK_ACCOUNT", XQUIK_ACCOUNT),
            "text": tweet_text,
            "reply_to_tweet_id": target_tweet_id,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{XQUIK_API_BASE.rstrip('/')}/x/tweets",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_body = response.read().decode("utf-8")
    response_data = json.loads(response_body)
    tweet_id = response_data.get("tweetId") or response_data.get("tweet_id")
    if not tweet_id:
        raise ValueError("Xquik response did not include a tweet id")
    return tweet_id


def post_reply(tweet_text):
    if TWITTER_BACKEND == "twitter":
        return post_with_twitter(tweet_text)
    if TWITTER_BACKEND == "xquik":
        return post_with_xquik(tweet_text)
    raise ValueError("TWITTER_BACKEND must be twitter or xquik")


def main():
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = get_reminder_message()
        tweet_text = f"({message['language']}) {message['text']} {now}]"

        tweet_id = post_reply(tweet_text)
        print(f"Reply posted successfully: {tweet_id} \n{tweet_text}")
    except tweepy.errors.Forbidden as e:
        details = e.api_messages if hasattr(e, "api_messages") else e
        print(f"Forbidden Error (403): {details}")
    except urllib.error.HTTPError as e:
        print(f"Xquik HTTP Error ({e.code}): {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
