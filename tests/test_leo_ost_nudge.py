import contextlib
import io
import json
import unittest
from unittest import mock

import leo_ost_nudge


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class LeoOstNudgeTest(unittest.TestCase):
    def test_require_env_rejects_missing_values(self):
        with self.assertRaisesRegex(ValueError, "API_KEY is required"):
            leo_ost_nudge.require_env("API_KEY", None)

    def test_post_reply_rejects_unknown_backend(self):
        with mock.patch.object(leo_ost_nudge, "TWITTER_BACKEND", "unknown"):
            with self.assertRaisesRegex(
                ValueError, "TWITTER_BACKEND must be twitter or xquik"
            ):
                leo_ost_nudge.post_reply("Reminder")

    def test_post_with_xquik_sends_expected_reply_request(self):
        response = FakeResponse(b'{"tweetId":"tweet-456"}')

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge.urllib.request,
                "urlopen",
                return_value=response,
            ) as urlopen,
        ):
            tweet_id = leo_ost_nudge.post_with_xquik("Reminder")

        request = urlopen.call_args.args[0]
        self.assertEqual(tweet_id, "tweet-456")
        self.assertEqual(request.full_url, "https://xquik.com/api/v1/x/tweets")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("X-api-key"), "xq_test")
        self.assertEqual(
            json.loads(request.data),
            {
                "account": "@leo",
                "reply_to_tweet_id": leo_ost_nudge.target_tweet_id,
                "text": "Reminder",
            },
        )
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 30})

    def test_post_with_xquik_does_not_echo_invalid_response(self):
        response = FakeResponse(b'{"secret":"do-not-echo"}')

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge.urllib.request,
                "urlopen",
                return_value=response,
            ),
            self.assertRaisesRegex(
                ValueError,
                "^Xquik response did not include a tweet id$",
            ),
        ):
            leo_ost_nudge.post_with_xquik("Reminder")

    def test_main_posts_one_generated_reminder(self):
        reminder = {"language": "English", "text": "Reminder"}
        output = io.StringIO()

        with (
            mock.patch.object(
                leo_ost_nudge, "get_reminder_message", return_value=reminder
            ),
            mock.patch.object(
                leo_ost_nudge, "post_reply", return_value="tweet-123"
            ) as post_reply,
            contextlib.redirect_stdout(output),
        ):
            leo_ost_nudge.main()

        post_reply.assert_called_once()
        self.assertIn("Reply posted successfully: tweet-123", output.getvalue())


if __name__ == "__main__":
    unittest.main()
