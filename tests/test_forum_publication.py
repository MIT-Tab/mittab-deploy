from datetime import date
import base64
import hashlib
import hmac
import json
from unittest.mock import patch, Mock

from test_public import AppTestCase

from deployer.clients import forum
from deployer.models import App

CONFIG = {
    "APDA_FORUM_URL": "https://forum.example.test",
    "NU_TAB_DOMAIN": "tab.example.test",
    "APDA_MITTAB_FORUM_SIGNING_KEY": "test-key",
}


@patch.dict("os.environ", CONFIG)
class ForumPublicationTest(AppTestCase):
    def test_only_a_real_apda_booking_gets_a_scoped_credential(self):
        app = App("example", "MIT-Tab/mit-tab", "master", date.today(), "tab@example.test")
        app.checkout_key = "a" * 32
        self.assertEqual(forum.publication_settings(app), {})
        app.forum_mode = "existing"
        app.forum_selection = "https://forum.example.test/forum/topic/example/"
        config = forum.publication_settings(app)
        payload, signature = config["APDA_FORUM_TOURNAMENT_TOKEN"].split(".")
        self.assertEqual(signature, hmac.new(b"test-key", payload.encode(), hashlib.sha256).hexdigest())
        self.assertEqual(
            json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))),
            {"id": app.checkout_key, "mode": "existing", "tab_url": app.url, "topic_url": app.forum_selection},
        )
        app.name = "example-test"
        self.assertEqual(forum.publication_settings(app), {})

    @patch("deployer.clients.forum.requests.post")
    def test_announcement_uses_fixed_endpoint_and_does_not_follow_redirects(self, post):
        post.return_value = Mock(status_code=201)
        topic = "https://forum.example.test/forum/topic/example/"
        post.return_value.json.return_value = {"status": "published", "url": topic}
        app = App("example", "MIT-Tab/mit-tab", "master", date.today(), "tab@example.test")
        app.checkout_key = "b" * 32
        app.forum_mode = "new"
        app.forum_selection = "Example Invitational"
        self.assertEqual(forum.announce(app), topic)
        self.assertEqual(
            post.call_args.args[0],
            f"https://forum.example.test/wp-json/apda-forum/v1/tournaments/{app.checkout_key}/announcement",
        )
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
