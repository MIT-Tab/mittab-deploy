import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "ci_watch", str(ROOT / "bin/ci-watch"))
spec = importlib.util.spec_from_loader(loader.name, loader)
watch = importlib.util.module_from_spec(spec)
loader.exec_module(watch)


class WatchTests(unittest.TestCase):
    def test_first_failure_returns_with_checks_still_running(self):
        pending = {"__typename": "CheckRun", "name": "Tests", "status": "IN_PROGRESS"}
        failures = [
            {"__typename": "CheckRun", "name": "Lint", "status": "COMPLETED",
             "conclusion": "FAILURE"},
            {"__typename": "StatusContext", "context": "Lint", "state": "FAILURE"},
        ]
        for failure in failures:
            with self.subTest(failure=failure):
                snapshot = {"headRefOid": "abc", "statusCheckRollup": [pending, failure]}
                with patch.object(watch, "gh_json", side_effect=[snapshot]), \
                        patch.object(watch.time, "sleep") as sleep:
                    sha, checks = watch.wait_for_checks(1, 60, 600)
                sleep.assert_not_called()
                passed, summary = watch.report(1, sha, checks, include_logs=False)
                self.assertFalse(passed)
                self.assertIn("Lint: FAILURE", summary)
                self.assertNotIn("Tests:", summary)

    def test_background_pass_writes_result_without_notifying(self):
        check = {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(watch, "STATE", Path(directory)), \
                patch.object(watch, "wait_for_checks", return_value=("abc", [check])), \
                patch.object(watch, "wake") as wake:
            args = SimpleNamespace(pr=1, interval=60, timeout=600, thread="current-chat")
            watch.background(args)
            wake.assert_not_called()
            self.assertIn("CI PASSED", (Path(directory) / "ci-watch-1.result").read_text())

    def test_background_notifies_before_fetching_logs(self):
        check = {"__typename": "CheckRun", "name": "Lint", "status": "COMPLETED",
                 "conclusion": "FAILURE"}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(watch, "STATE", Path(directory)), \
                patch.object(watch, "wait_for_checks", return_value=("abc", [check])), \
                patch.object(watch, "wake") as wake, \
                patch.object(watch, "actions_log_tail") as fetch_logs:
            def fetch_tail(*_args):
                wake.assert_called_once()
                return "failure details"

            fetch_logs.side_effect = fetch_tail
            args = SimpleNamespace(pr=1, interval=60, timeout=600, thread="current-chat")
            watch.background(args)
            fetch_logs.assert_called_once()
            thread, message, _ = wake.call_args.args
            self.assertEqual(thread, "current-chat")
            self.assertIn("Lint: FAILURE", message)
            self.assertIn("failure details", (Path(directory) / "ci-watch-1.log").read_text())
