import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from requests import HTTPError


REQUIRED_ENV = {
    "DIGITALOCEAN_ACCESS_KEY_ID": "spaces-access-key",
    "DIGITALOCEAN_ACCESS_KEY_SECRET": "spaces-secret-key",
    "DIGITALOCEAN_TOKEN": "digitalocean-token",
}


with patch.dict(os.environ, REQUIRED_ENV):
    module_path = (
        Path(__file__).resolve().parents[1] / "deployer" / "clients" / "digital_ocean.py"
    )
    module_spec = importlib.util.spec_from_file_location("digital_ocean", module_path)
    digital_ocean = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(digital_ocean)


class BuildAppSpecTest(unittest.TestCase):
    def build_spec(self, repo_slug="MIT-Tab/mit-tab"):
        return getattr(digital_ocean, "__build_app_spec")(
            "test-tournament",
            "tab-password",
            {
                "name": "test-database",
                "connection": {"database": "defaultdb", "user": "doadmin"},
            },
            repo_slug,
            "master",
        )

    def envs_by_key(self, spec):
        return {env["key"]: env for env in spec["envs"]}

    def test_injects_board_and_aws_ses_secrets(self):
        tournament_env = {
            "BOARD_PASSWORD": "board-password",
            "AWS_SES_ACCESS_KEY_ID": "ses-access-key",
            "AWS_SES_SECRET_ACCESS_KEY": "ses-secret-key",
            "AWS_SES_REGION": "us-west-2",
            "AWS_SES_CONFIGURATION_SET": "transactional-email",
            "AWS_MAILMANAGER_ADDRESS_LIST": "registered-users",
            "EMAIL_FROM_ADDRESS": "tab@example.com",
            "EMAIL_FROM_NAME": "Tab Team",
            "EMAIL_REPLY_TO": "help@example.com",
            "BLACK_ROD_API_BASE_URL": "https://results.example.test",
            "BLACK_ROD_PRIVATE_API_TOKEN": "live-token",
        }
        with patch.dict(os.environ, tournament_env, clear=False):
            envs = self.envs_by_key(self.build_spec())

        for key in (
            "BOARD_PASSWORD",
            "AWS_SES_ACCESS_KEY_ID",
            "AWS_SES_SECRET_ACCESS_KEY",
        ):
            self.assertEqual(envs[key]["type"], "SECRET")

        self.assertEqual(envs["BOARD_PASSWORD"]["value"], "board-password")
        self.assertEqual(envs["AWS_SES_ACCESS_KEY_ID"]["value"], "ses-access-key")
        self.assertEqual(
            envs["AWS_SES_SECRET_ACCESS_KEY"]["value"], "ses-secret-key"
        )
        self.assertEqual(envs["AWS_SES_REGION"]["value"], "us-west-2")
        self.assertEqual(
            envs["AWS_SES_CONFIGURATION_SET"]["value"], "transactional-email"
        )
        self.assertEqual(
            envs["AWS_MAILMANAGER_ADDRESS_LIST"]["value"], "registered-users"
        )
        self.assertEqual(envs["EMAIL_FROM_ADDRESS"]["value"], "tab@example.com")
        self.assertEqual(envs["EMAIL_FROM_NAME"]["value"], "Tab Team")
        self.assertEqual(envs["EMAIL_REPLY_TO"]["value"], "help@example.com")
        self.assertEqual(
            envs["BLACK_ROD_API_BASE_URL"]["value"],
            "https://results.example.test",
        )
        self.assertEqual(envs["BLACK_ROD_PRIVATE_API_TOKEN"]["value"], "live-token")
        self.assertEqual(envs["BLACK_ROD_PRIVATE_API_TOKEN"]["type"], "SECRET")

    def test_provisions_tabgpt_in_tournament_web_runtime(self):
        with patch.dict(os.environ, {
            "MITTAB_ASSISTANT_ENABLED": "1",
            "MITTAB_ASSISTANT_ACCOUNT_ID": "a" * 32,
            "MITTAB_ASSISTANT_API_TOKEN": "workers-ai-token",
        }):
            spec = self.build_spec()

        envs = {env["key"]: env for env in spec["services"][0]["envs"]}
        self.assertEqual(envs["MITTAB_ASSISTANT_API_TOKEN"], {
            "key": "MITTAB_ASSISTANT_API_TOKEN",
            "value": "workers-ai-token",
            "scope": "RUN_TIME",
            "type": "SECRET",
        })
        self.assertEqual(envs["MITTAB_ASSISTANT_ENABLED"]["value"], "1")
        self.assertEqual(envs["MITTAB_ASSISTANT_ACCOUNT_ID"]["value"], "a" * 32)
        self.assertEqual(envs["MITTAB_SOURCE_REVISION"]["value"], "${_self.COMMIT_HASH}")
        self.assertTrue(all(env["scope"] == "RUN_TIME" for env in envs.values()))
        self.assertTrue(envs.keys().isdisjoint(self.envs_by_key(spec)))
        self.assertTrue(all("envs" not in site for site in spec["static_sites"]))

    def test_tabgpt_defaults_off_and_requires_both_credentials_for_forwarding(self):
        for account_id, token in (("", ""), ("a" * 32, ""), ("", "workers-ai-token")):
            with self.subTest(account_id=account_id, has_token=bool(token)), patch.dict(
                os.environ, {
                    "MITTAB_ASSISTANT_ENABLED": "1",
                    "MITTAB_ASSISTANT_ACCOUNT_ID": account_id,
                    "MITTAB_ASSISTANT_API_TOKEN": token,
                },
            ):
                self.assertNotIn("envs", self.build_spec()["services"][0])

        with patch.dict(os.environ, {
            "MITTAB_ASSISTANT_ENABLED": "",
            "MITTAB_ASSISTANT_ACCOUNT_ID": "a" * 32,
            "MITTAB_ASSISTANT_API_TOKEN": "workers-ai-token",
        }):
            spec = self.build_spec()
            fork = self.build_spec(repo_slug="example/mit-tab")

        web_envs = {env["key"]: env["value"] for env in spec["services"][0]["envs"]}
        self.assertEqual(web_envs["MITTAB_ASSISTANT_ENABLED"], "0")
        self.assertNotIn("envs", fork["services"][0])

    def test_app_creation_error_does_not_log_response_payload(self):
        response = Mock()
        response.raise_for_status.side_effect = HTTPError("invalid app spec")
        response.json.return_value = {"message": "reflected test credential"}

        with patch.object(digital_ocean.requests, "post", return_value=response), \
                self.assertLogs(digital_ocean.logger, level="INFO") as logs, \
                self.assertRaises(HTTPError):
            digital_ocean.create_app(
                "test-tournament", "tab-password", {"name": "db", "connection": {
                    "database": "defaultdb", "user": "doadmin",
                }}, "MIT-Tab/mit-tab", "master",
            )

        response.json.assert_not_called()
        self.assertNotIn("reflected test credential", "\n".join(logs.output))

    def test_does_not_inject_partial_aws_ses_credentials(self):
        empty_optional_env = {
            "BOARD_PASSWORD": "",
            "AWS_SES_ACCESS_KEY_ID": "ses-access-key",
            "AWS_SES_SECRET_ACCESS_KEY": "",
            "AWS_SES_REGION": "",
            "AWS_SES_CONFIGURATION_SET": "",
            "AWS_MAILMANAGER_ADDRESS_LIST": "",
            "EMAIL_FROM_ADDRESS": "",
            "EMAIL_FROM_NAME": "",
            "EMAIL_REPLY_TO": "",
            "BLACK_ROD_API_BASE_URL": "",
            "BLACK_ROD_PRIVATE_API_TOKEN": "",
            "NU_TAB_DOMAIN": "",
        }
        with patch.dict(os.environ, empty_optional_env, clear=False):
            envs = self.envs_by_key(self.build_spec())

        self.assertNotIn("BOARD_PASSWORD", envs)
        self.assertNotIn("AWS_SES_ACCESS_KEY_ID", envs)
        self.assertNotIn("AWS_SES_SECRET_ACCESS_KEY", envs)
        self.assertNotIn("AWS_SES_REGION", envs)


class WaitForAppTest(unittest.TestCase):
    def test_waits_for_active_app_and_returns_default_ingress_while_dns_is_pending(self):
        temporary_url = "https://fall-open-example.ondigitalocean.app"
        responses = [
            {"app": {"in_progress_deployment": {"phase": "BUILDING"}}},
            {"app": {"active_deployment": {"phase": "ACTIVE"}}},
            {"app": {
                "active_deployment": {"phase": "ACTIVE"},
                "default_ingress": temporary_url,
                "live_url": "https://fall-open.nu-tab.com",
                "domains": [{"phase": "PENDING"}],
            }},
        ]
        with patch.object(digital_ocean, "__get", side_effect=responses) as get_app, \
                patch.object(digital_ocean, "sleep") as sleep:
            result = digital_ocean.wait_for_app("app-id", timeout=90)

        self.assertEqual(result, temporary_url)
        self.assertEqual(get_app.call_count, 3)
        get_app.assert_called_with("apps/app-id")
        self.assertEqual(sleep.call_count, 2)

    def test_does_not_report_building_app_as_deployed_even_if_it_has_a_url(self):
        response = {"app": {
            "active_deployment": None,
            "in_progress_deployment": {"phase": "BUILDING"},
            "default_ingress": "https://fall-open-example.ondigitalocean.app",
        }}
        with patch.object(digital_ocean, "__get", return_value=response), \
                patch.object(digital_ocean, "sleep"):
            with self.assertRaisesRegex(ValueError, "Timed out"):
                digital_ocean.wait_for_app("app-id", timeout=30)

    def test_failed_or_canceled_deployment_stops_waiting(self):
        for phase in ("ERROR", "CANCELED"):
            with self.subTest(phase=phase), \
                    patch.object(digital_ocean, "__get", return_value={"app": {
                        "in_progress_deployment": {"phase": phase},
                    }}), patch.object(digital_ocean, "sleep") as sleep:
                with self.assertRaisesRegex(ValueError, "failed"):
                    digital_ocean.wait_for_app("app-id")
                sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
