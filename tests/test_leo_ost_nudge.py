import contextlib
import io
import json
import unittest
from unittest import mock

import leo_ost_nudge


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

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
        with (
            mock.patch.object(leo_ost_nudge, "TWITTER_BACKEND", "unknown"),
            self.assertRaisesRegex(
                ValueError, "TWITTER_BACKEND must be twitter or xquik"
            ),
        ):
            leo_ost_nudge.post_reply("Reminder")

    def test_post_with_xquik_sends_expected_reply_request(self):
        response = FakeResponse(
            b'{"terminal":true,"success":true,"tweet_id":"tweet-456"}'
        )

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge,
                "XQUIK_IDEMPOTENCY_KEY",
                "reply-attempt-1",
            ),
            mock.patch.object(
                leo_ost_nudge,
                "open_without_redirects",
                return_value=response,
            ) as open_request,
        ):
            tweet_id = leo_ost_nudge.post_with_xquik("Reminder")

        request = open_request.call_args.args[0]
        self.assertEqual(tweet_id, "tweet-456")
        self.assertEqual(request.full_url, "https://xquik.com/api/v1/x/tweets")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Idempotency-key"), "reply-attempt-1")
        self.assertEqual(request.get_header("X-api-key"), "xq_test")
        self.assertEqual(
            request.get_header("Xquik-api-contract"),
            leo_ost_nudge.XQUIK_API_CONTRACT,
        )
        self.assertEqual(
            json.loads(request.data),
            {
                "account": "@leo",
                "reply_to_tweet_id": leo_ost_nudge.target_tweet_id,
                "text": "Reminder",
            },
        )
        self.assertEqual(
            open_request.call_args.kwargs,
            {"timeout": leo_ost_nudge.XQUIK_REQUEST_TIMEOUT_SECONDS},
        )

    def test_post_with_xquik_does_not_echo_invalid_response(self):
        response = FakeResponse(b'{"secret":"do-not-echo"}')

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge,
                "XQUIK_IDEMPOTENCY_KEY",
                "reply-attempt-1",
            ),
            mock.patch.object(
                leo_ost_nudge,
                "open_without_redirects",
                return_value=response,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "^Xquik request failed with status 200$",
            ),
        ):
            leo_ost_nudge.post_with_xquik("Reminder")

    def test_post_with_xquik_reports_pending_recovery(self):
        response = FakeResponse(
            b'{"write_action_id":"42","status_url":"/api/v1/x/write-actions/42"}',
            status=202,
        )

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge,
                "XQUIK_IDEMPOTENCY_KEY",
                "reply-attempt-1",
            ),
            mock.patch.object(
                leo_ost_nudge,
                "open_without_redirects",
                return_value=response,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "confirmation is pending.*write-actions/42",
            ),
        ):
            leo_ost_nudge.post_with_xquik("Reminder")

    def test_generated_idempotency_key_is_stable_for_the_same_payload(self):
        with mock.patch.object(leo_ost_nudge, "XQUIK_IDEMPOTENCY_KEY", None):
            first = leo_ost_nudge.resolve_idempotency_key(b"first payload")
            repeated = leo_ost_nudge.resolve_idempotency_key(b"first payload")
            different = leo_ost_nudge.resolve_idempotency_key(b"second payload")

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, different)
        self.assertTrue(first.startswith("leo-ost-nudge:"))

    def test_post_with_xquik_rejects_invalid_configured_idempotency_key(self):
        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge,
                "XQUIK_IDEMPOTENCY_KEY",
                "invalid key",
            ),
            self.assertRaisesRegex(ValueError, "visible ASCII"),
        ):
            leo_ost_nudge.post_with_xquik("Reminder")

    def test_http_error_preserves_recovery_without_echoing_body(self):
        error = leo_ost_nudge.urllib.error.HTTPError(
            "https://xquik.com/api/v1/x/tweets",
            503,
            "Unavailable",
            {},
            io.BytesIO(
                b'{"status_url":"/api/v1/x/write-actions/42",'
                b'"safe_to_retry":false,"secret":"do-not-echo"}'
            ),
        )

        with (
            mock.patch.object(leo_ost_nudge, "XQUIK_API_KEY", "xq_test"),
            mock.patch.object(leo_ost_nudge, "XQUIK_ACCOUNT", "@leo"),
            mock.patch.object(
                leo_ost_nudge,
                "XQUIK_IDEMPOTENCY_KEY",
                "reply-attempt-1",
            ),
            mock.patch.object(
                leo_ost_nudge,
                "open_without_redirects",
                side_effect=error,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "status 503.*write-actions/42.*Do not submit",
            ) as raised,
        ):
            leo_ost_nudge.post_with_xquik("Reminder")

        self.assertNotIn("do-not-echo", str(raised.exception))

    def test_redirect_handler_refuses_redirects(self):
        self.assertIsNone(
            leo_ost_nudge.RejectRedirects().redirect_request(
                object(),
                None,
                302,
                "Found",
                {},
                "https://attacker.invalid/capture",
            )
        )

    def test_default_opener_rejects_redirects_and_honors_timeout(self):
        request = object()
        response = object()
        with mock.patch.object(
            leo_ost_nudge.urllib.request, "build_opener"
        ) as build_opener:
            build_opener.return_value.open.return_value = response

            self.assertIs(
                leo_ost_nudge.open_without_redirects(request, timeout=70),
                response,
            )

        handler = build_opener.call_args.args[0]
        self.assertIsInstance(handler, leo_ost_nudge.RejectRedirects)
        build_opener.return_value.open.assert_called_once_with(request, timeout=70)

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
            result = leo_ost_nudge.main()

        post_reply.assert_called_once()
        self.assertEqual(result, 0)
        self.assertIn("Reply posted successfully: tweet-123", output.getvalue())

    def test_main_returns_failure_without_echoing_response_body(self):
        output = io.StringIO()

        with (
            mock.patch.object(
                leo_ost_nudge,
                "get_reminder_message",
                return_value={"language": "English", "text": "Reminder"},
            ),
            mock.patch.object(
                leo_ost_nudge,
                "post_reply",
                side_effect=RuntimeError("Xquik request failed with status 503"),
            ),
            contextlib.redirect_stdout(output),
        ):
            result = leo_ost_nudge.main()

        self.assertEqual(result, 1)
        self.assertEqual(
            output.getvalue().strip(),
            "Error: Xquik request failed with status 503",
        )


if __name__ == "__main__":
    unittest.main()
