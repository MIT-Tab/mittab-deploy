import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


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
    def build_spec(self):
        return getattr(digital_ocean, "__build_app_spec")(
            "test-tournament",
            "tab-password",
            {
                "name": "test-database",
                "connection": {"database": "defaultdb", "user": "doadmin"},
            },
            "MIT-Tab/mit-tab",
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


if __name__ == "__main__":
    unittest.main()
