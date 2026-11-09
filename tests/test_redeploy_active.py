"""Fleet rollout tests run without Flask, credentials, or live API calls."""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "redeploy_active.py"
SPEC = importlib.util.spec_from_file_location("redeploy_active", MODULE_PATH)
redeploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(redeploy)


def tournament(name="alpha", branch="master"):
    return {
        "id": name + "-id",
        "spec": {
            "name": "mittab-" + name,
            "services": [{"name": "web", "github": {"repo": "MIT-Tab/mit-tab", "branch": branch}}],
            "static_sites": [{"name": "static", "github": {"repo": "MIT-Tab/mit-tab", "branch": branch}}],
            "envs": [{"key": "TAB_PASSWORD", "value": "secret"}],
            "databases": [{"name": "existing-database"}],
        },
        "active_deployment": {"id": "old-deployment", "phase": "ACTIVE"},
    }


class TargetSelectionTest(unittest.TestCase):
    def test_only_matching_live_tournaments_are_selected(self):
        active = tournament()
        beta = tournament("beta", "discord")
        test = tournament("alpha-test")
        unrelated = tournament("other")
        unrelated["spec"]["name"] = "deployer"
        wrong_repo = tournament("fork")
        wrong_repo["spec"]["services"][0]["github"]["repo"] = "someone/fork"
        inactive = tournament("inactive")
        inactive["active_deployment"] = None
        pending = tournament("pending")
        pending["pending_deployment"] = {"id": "pending-id"}
        busy = tournament("busy")
        busy["in_progress_deployment"] = {"id": "busy-id"}
        pinned = tournament("pinned")
        pinned["pinned_deployment"] = {"id": "rollback-id"}
        targets, skipped = redeploy.select_apps(
            [test, unrelated, beta, wrong_repo, inactive, pending, busy, pinned, active], "master", False
        )
        self.assertEqual(targets, [active])
        self.assertEqual(len(skipped), 7)
        self.assertTrue(all(row.status == "Skipped" for row in skipped))

    def test_all_branches_and_tests_are_opt_in(self):
        apps = [tournament(), tournament("beta", "discord"), tournament("alpha-test")]
        targets, skipped = redeploy.select_apps(apps, "all", True)
        self.assertEqual(len(targets), 3)
        self.assertEqual(skipped, [])
        targets, _ = redeploy.select_apps(apps, "discord", True)
        self.assertEqual([app["spec"]["name"] for app in targets], ["mittab-beta"])

    def test_every_component_must_match_repository_and_branch(self):
        for source in ({"repo": "MIT-Tab/mit-tab", "branch": "discord"}, {}, {"repo": "someone/fork", "branch": "master"}):
            with self.subTest(source=source):
                app = tournament()
                app["spec"]["static_sites"][0]["github"] = source
                self.assertTrue(redeploy.skip_reason(app, "all", True))

    def test_repository_comparison_is_case_insensitive(self):
        app = tournament()
        app["spec"]["services"][0]["github"]["repo"] = "mit-tab/MIT-TAB"
        self.assertEqual(redeploy.skip_reason(app, "master", False), "")


class APITest(unittest.TestCase):
    def test_all_pages_are_read_and_duplicate_ids_are_deduplicated(self):
        client = redeploy.DigitalOcean("token")
        client.request = Mock(side_effect=[
            {"apps": [tournament()], "links": {"pages": {"next": "https://untrusted.invalid/page2"}}},
            {"apps": [tournament(), tournament("beta")], "links": {}},
        ])
        self.assertEqual(len(client.list_apps()), 2)
        self.assertEqual(client.request.call_args_list[1].args, ("GET", "/apps?per_page=200&page=2"))

    @patch.object(redeploy, "urlopen")
    def test_create_deployment_sends_only_build_option(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"deployment": {"id": "new-deployment"}}'
        redeploy.DigitalOcean("token").create_deployment("app-id", False)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, redeploy.API_URL + "/apps/app-id/deployments")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"force_build": False})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    @patch.object(redeploy.time, "sleep")
    @patch.object(redeploy, "urlopen")
    def test_transient_get_is_retried_but_post_is_never_retried(self, urlopen, sleep):
        urlopen.side_effect = HTTPError("url", 503, "unavailable", {}, None)
        client = redeploy.DigitalOcean("token")
        with self.assertRaises(redeploy.DeploymentError):
            client.request("GET", "/apps")
        self.assertEqual(urlopen.call_count, 3)
        urlopen.reset_mock()
        with self.assertRaises(redeploy.DeploymentError):
            client.request("POST", "/apps/id/deployments", {})
        self.assertEqual(urlopen.call_count, 1)

    @patch.object(redeploy, "urlopen", side_effect=URLError("secret-response-body"))
    def test_transport_errors_do_not_log_sensitive_details(self, urlopen):
        with self.assertRaises(redeploy.DeploymentError) as caught:
            redeploy.DigitalOcean("secret-token").request("GET", "/apps")
        self.assertNotIn("secret", str(caught.exception))

    @patch.object(redeploy.time, "sleep")
    def test_waits_for_active_and_stops_on_failure(self, sleep):
        client = redeploy.DigitalOcean("token")
        client.request = Mock(side_effect=[
            {"deployment": {"phase": "BUILDING"}}, {"deployment": {"phase": "ACTIVE"}},
        ])
        client.wait_for_deployment("app-id", "new-deployment", 1800)
        self.assertEqual(client.request.call_count, 2)
        for phase in redeploy.FAILED_PHASES:
            client.request = Mock(return_value={"deployment": {"phase": phase}})
            with self.assertRaisesRegex(redeploy.DeploymentError, phase):
                client.wait_for_deployment("app-id", "new-deployment", 1800)

    @patch.object(redeploy.time, "monotonic", side_effect=[0, 2])
    def test_timeout_is_an_error_without_canceling_the_deployment(self, monotonic):
        client = redeploy.DigitalOcean("token")
        client.request = Mock()
        with self.assertRaisesRegex(redeploy.DeploymentError, "may still be running"):
            client.wait_for_deployment("app-id", "new-deployment", 1)
        client.request.assert_not_called()


class RolloutTest(unittest.TestCase):
    def setUp(self):
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.apps = [tournament(name) for name in ("alpha", "beta", "gamma", "delta", "epsilon")]
        self.client = Mock()
        by_id = {app["id"]: app for app in self.apps}
        self.client.get_app.side_effect = lambda app_id: deepcopy(by_id[app_id])
        self.client.create_deployment.side_effect = lambda app_id, force: {"id": "new-" + app_id}
        self.results = []

    def run_rollout(self, *flags):
        return redeploy.rollout(self.client, self.apps, self.results, redeploy.parse_args(list(flags)))

    def test_preview_has_no_mutating_calls(self):
        self.assertEqual(self.run_rollout(), 0)
        self.client.get_app.assert_not_called()
        self.client.create_deployment.assert_not_called()
        self.assertTrue(all(row.status == "Would deploy" for row in self.results))

    def test_canary_completes_before_remainder_starts(self):
        self.assertEqual(self.run_rollout("--execute", "--canary", "mittab-gamma", "--batch-size", "2"), 0)
        calls = self.client.method_calls
        self.assertEqual(calls[0].args, ("gamma-id",))
        self.assertEqual(calls[1].args, ("gamma-id", False))
        self.assertEqual(calls[2].args, ("gamma-id", "new-gamma-id", 1800))
        self.assertEqual(self.client.create_deployment.call_count, len(self.apps))
        self.assertTrue(all(row.status == "Succeeded" for row in self.results))

    def test_failed_canary_prevents_all_other_deployments(self):
        self.client.wait_for_deployment.side_effect = redeploy.DeploymentError("failed canary")
        self.assertEqual(self.run_rollout("--execute"), 1)
        self.assertEqual(self.client.create_deployment.call_count, 1)
        self.assertEqual(self.results[0].status, "Failed")
        self.assertEqual(self.results[0].deployment_id, "new-alpha-id")
        self.assertTrue(all(row.status == "Not started" for row in self.results[1:]))

    def test_batch_failure_finishes_current_batch_but_stops_later_batches(self):
        def wait(app_id, deployment_id, timeout):
            if app_id == "beta-id":
                raise redeploy.DeploymentError("build failed")
        self.client.wait_for_deployment.side_effect = wait
        self.assertEqual(self.run_rollout("--execute", "--batch-size", "2"), 1)
        self.assertEqual(self.client.create_deployment.call_count, 3)
        self.assertEqual([row.status for row in self.results], ["Succeeded", "Failed", "Succeeded", "Not started", "Not started"])

    def test_changed_or_busy_canary_is_skipped_without_post(self):
        for change in ("spec", "active", "busy"):
            with self.subTest(change=change):
                fresh = deepcopy(self.apps[0])
                if change == "spec":
                    fresh["spec"]["envs"][0]["value"] = "new-secret"
                elif change == "active":
                    fresh["active_deployment"]["id"] = "someone-elses-deployment"
                else:
                    fresh["in_progress_deployment"] = {"id": "another-deployment"}
                self.client.get_app.side_effect = None
                self.client.get_app.return_value = fresh
                self.results = []
                self.assertEqual(self.run_rollout("--execute"), 1)
                self.client.create_deployment.assert_not_called()
                self.assertEqual(self.results[0].status, "Skipped")

    def test_invalid_canary_and_empty_targets_fail_without_deploying(self):
        with self.assertRaises(redeploy.DeploymentError):
            self.run_rollout("--execute", "--canary", "mittab-does-not-exist")
        self.apps = []
        with self.assertRaises(redeploy.DeploymentError):
            self.run_rollout("--execute")
        self.client.create_deployment.assert_not_called()

    def test_api_failure_is_recorded_and_stops_rollout(self):
        self.client.create_deployment.side_effect = redeploy.DeploymentError("HTTP 403")
        self.assertEqual(self.run_rollout("--execute"), 1)
        self.assertEqual(self.results[0].status, "Failed")
        self.assertEqual(self.results[0].detail, "HTTP 403")

    def test_skipped_discovery_rows_remain_in_the_final_summary(self):
        skipped = redeploy.Result("test-id", "mittab-alpha-test", "Skipped", "Test servers excluded")
        self.results.append(skipped)
        self.assertEqual(self.run_rollout("--execute", "--force-build"), 0)
        self.assertIs(self.results[0], skipped)
        self.assertTrue(all(row.status == "Succeeded" for row in self.results[1:]))
        self.assertTrue(all(call.args[1] for call in self.client.create_deployment.call_args_list))


class CommandTest(unittest.TestCase):
    @patch.object(redeploy, "DigitalOcean")
    def test_command_discovers_only_eligible_apps_and_previews_by_default(self, client_class):
        client = client_class.return_value
        client.list_apps.return_value = [tournament(), tournament("alpha-test"), tournament("beta", "discord")]
        with patch.dict(os.environ, {"DIGITALOCEAN_TOKEN": "test-token"}, clear=True), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(redeploy.main([]), 0)
        client.create_deployment.assert_not_called()
        self.assertIn("Would deploy", output.getvalue())
        self.assertIn("Test servers excluded", output.getvalue())
        self.assertIn("Uses another branch: discord", output.getvalue())

    def test_missing_token_fails_with_actionable_summary(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(redeploy.main([]), 1)
        self.assertIn("Set DIGITALOCEAN_TOKEN", output.getvalue())

    def test_github_summary_contains_results_and_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), redirect_stdout(io.StringIO()):
                redeploy.write_summary([
                    redeploy.Result("id", "mittab-alpha", "Succeeded", "ACTIVE", "new-id"),
                    redeploy.Result("test-id", "mittab-alpha-test", "Skipped", "Test servers excluded"),
                ])
            text = summary.read_text()
        self.assertIn("Succeeded", text)
        self.assertIn("Test servers excluded", text)
        self.assertIn("new-id", text)
        self.assertIn("https://cloud.digitalocean.com/apps/id", text)


if __name__ == "__main__":
    unittest.main()
