import datetime
import hashlib
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
XQUIK_IDEMPOTENCY_KEY = os.environ.get("XQUIK_IDEMPOTENCY_KEY")

XQUIK_API_BASE = "https://xquik.com/api/v1"
XQUIK_API_CONTRACT = "2026-04-29"
XQUIK_REQUEST_TIMEOUT_SECONDS = 70

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
    except (OSError, TypeError, ValueError) as error:
        print(error)
        return {
            "text": "@anirudhofficial bro, gentle reminder. [Sent at ",
            "language": "English",
        }


def require_env(name, value):
    if not value:
        raise ValueError(f"{name} is required")
    return value


def validate_idempotency_key(value):
    invalid_character = any(
        ord(character) < 33 or ord(character) > 126 for character in value
    )
    if not 1 <= len(value) <= 255 or invalid_character:
        raise ValueError(
            "XQUIK_IDEMPOTENCY_KEY must contain 1-255 visible ASCII characters"
        )
    return value


def resolve_idempotency_key(payload):
    configured_key = (XQUIK_IDEMPOTENCY_KEY or "").strip()
    if configured_key:
        return validate_idempotency_key(configured_key)
    digest = hashlib.sha256(payload).hexdigest()
    return f"leo-ost-nudge:{digest}"


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_without_redirects(request, timeout):
    opener = urllib.request.build_opener(RejectRedirects())
    return opener.open(request, timeout=timeout)


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
    idempotency_key = resolve_idempotency_key(payload)
    request = urllib.request.Request(
        f"{XQUIK_API_BASE}/x/tweets",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "x-api-key": api_key,
            "xquik-api-contract": XQUIK_API_CONTRACT,
        },
        method="POST",
    )
    try:
        with open_without_redirects(
            request,
            timeout=XQUIK_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            return parse_xquik_write_response(response.status, response.read())
    except urllib.error.HTTPError as error:
        payload = parse_json_object(error.read())
        raise RuntimeError(xquik_failure_message(error.code, payload)) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Xquik request failed before confirmation. "
            "Retry only this exact reply. It reuses the same idempotency key"
        ) from error
    except TimeoutError as error:
        raise RuntimeError(
            "Xquik request timed out before confirmation. "
            "Retry only this exact reply. It reuses the same idempotency key"
        ) from error


def parse_xquik_write_response(status_code, body):
    payload = parse_json_object(body)
    if (
        status_code == 200
        and payload.get("terminal") is True
        and payload.get("success") is True
    ):
        result = payload.get("result")
        nested_id = result.get("id") if isinstance(result, dict) else None
        tweet_id = payload.get("tweet_id") or payload.get("tweetId") or nested_id
        if tweet_id:
            return tweet_id

    if status_code == 202:
        action_id = (
            payload.get("write_action_id")
            or payload.get("writeActionId")
            or payload.get("id")
        )
        status_url = payload.get("status_url") or payload.get("statusUrl")
        if action_id and status_url:
            raise RuntimeError(
                "Xquik accepted the reply, but confirmation is pending. "
                f"Do not submit a new write. Check {status_url} for action {action_id}. "
                "Do not retry while it remains pending"
            )

    raise RuntimeError(xquik_failure_message(status_code, payload))


def xquik_failure_message(status_code, payload):
    result = f"Xquik request failed with status {status_code}"
    status_url = payload.get("status_url") or payload.get("statusUrl")
    if status_url:
        result += f". Check {status_url} before retrying"
    safe_to_retry = payload.get("safe_to_retry")
    if safe_to_retry is None:
        safe_to_retry = payload.get("safeToRetry")
    if safe_to_retry is False:
        result += ". Do not submit a new write. Reuse the same idempotency key"
    return result


def parse_json_object(body):
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def post_reply(tweet_text):
    if TWITTER_BACKEND == "twitter":
        return post_with_twitter(tweet_text)
    if TWITTER_BACKEND == "xquik":
        return post_with_xquik(tweet_text)
    raise ValueError("TWITTER_BACKEND must be twitter or xquik")


def main():
    try:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        message = get_reminder_message()
        tweet_text = f"({message['language']}) {message['text']} {now}]"

        tweet_id = post_reply(tweet_text)
        print(f"Reply posted successfully: {tweet_id} \n{tweet_text}")
    except tweepy.errors.Forbidden as e:
        details = e.api_messages if hasattr(e, "api_messages") else e
        print(f"Forbidden Error (403): {details}")
        return 1
    except (KeyError, RuntimeError, TypeError, ValueError, tweepy.TweepyException) as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
