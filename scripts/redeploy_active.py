#!/usr/bin/env python3
"""Manually roll out the latest source to existing MITTab App Platform apps."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_URL = "https://api.digitalocean.com/v2"
REPOSITORY = "MIT-Tab/mit-tab"
COMPONENT_TYPES = ("services", "static_sites", "workers", "jobs", "functions")
FAILED_PHASES = {"ERROR", "FAILED", "CANCELED", "SUPERSEDED"}


class DeploymentError(Exception):
    pass


class DigitalOcean:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, body=None):
        request = Request(
            API_URL + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
            method=method,
        )
        # Never retry POST: a lost response may already have created a deployment.
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if method == "GET" and error.code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                # Do not log response bodies: app responses can contain secrets.
                raise DeploymentError("{} {} returned HTTP {}".format(method, path, error.code)) from None
            except (URLError, OSError, ValueError):
                raise DeploymentError("{} {} failed; check DigitalOcean before retrying".format(method, path)) from None

    def list_apps(self):
        apps = {}
        page = 1
        while True:
            response = self.request("GET", "/apps?per_page=200&page={}".format(page))
            for app in response["apps"]:
                apps[app["id"]] = app
            if not response.get("links", {}).get("pages", {}).get("next"):
                return list(apps.values())
            # Keep requests on the fixed API host rather than following supplied URLs.
            page += 1

    def get_app(self, app_id):
        return self.request("GET", "/apps/" + quote(app_id, safe=""))["app"]

    def create_deployment(self, app_id, force_build):
        path = "/apps/{}/deployments".format(quote(app_id, safe=""))
        return self.request("POST", path, {"force_build": force_build})["deployment"]

    def wait_for_deployment(self, app_id, deployment_id, timeout):
        path = "/apps/{}/deployments/{}".format(
            quote(app_id, safe=""), quote(deployment_id, safe="")
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            phase = self.request("GET", path)["deployment"].get("phase")
            if phase == "ACTIVE":
                return
            if phase in FAILED_PHASES:
                raise DeploymentError("Deployment ended in phase " + phase)
            time.sleep(min(10, max(0, deadline - time.monotonic())))
        raise DeploymentError("Timed out waiting; deployment may still be running")


@dataclass
class Result:
    app_id: str
    name: str
    status: str
    detail: str = ""
    deployment_id: str = ""

    @property
    def url(self):
        return "https://cloud.digitalocean.com/apps/{}".format(self.app_id)


def skip_reason(app, branch, include_tests):
    spec = app.get("spec", {})
    name = spec.get("name", "")
    if not name.startswith("mittab-"):
        return "Not a tournament app"
    if name.endswith("-test") and not include_tests:
        return "Test servers excluded"

    components = [component for kind in COMPONENT_TYPES for component in spec.get(kind, [])]
    if not spec.get("services") or not components:
        return "No tournament service"
    sources = [component.get("github", {}) for component in components]
    if any(source.get("repo", "").lower() != REPOSITORY.lower() for source in sources):
        return "Components do not all use " + REPOSITORY
    branches = {source.get("branch") for source in sources}
    if len(branches) != 1 or None in branches or "" in branches:
        return "Components have missing or mixed branches"
    if branch != "all" and branches != {branch}:
        return "Uses another branch: " + next(iter(branches))
    if app.get("pinned_deployment"):
        return "Deployment is pinned"
    if (app.get("active_deployment") or {}).get("phase") != "ACTIVE":
        return "No active deployment"
    if app.get("in_progress_deployment") or app.get("pending_deployment"):
        return "Deployment already in progress"
    return ""


def select_apps(apps, branch, include_tests):
    targets, results = [], []
    for app in sorted(apps, key=lambda app: app.get("spec", {}).get("name", "")):
        name = app.get("spec", {}).get("name", "")
        if not name.startswith("mittab-"):
            continue
        reason = skip_reason(app, branch, include_tests)
        if reason:
            results.append(Result(app["id"], name, "Skipped", reason))
        else:
            targets.append(app)
    return targets, results


def deploy_one(client, app, branch, include_tests, force_build, timeout):
    result = Result(app["id"], app["spec"]["name"], "Failed")
    try:
        fresh = client.get_app(app["id"])
        reason = skip_reason(fresh, branch, include_tests)
        if not reason and (
            fresh["spec"] != app["spec"]
            or fresh["active_deployment"]["id"] != app["active_deployment"]["id"]
        ):
            reason = "App changed since discovery; preview again"
        if reason:
            result.status, result.detail = "Skipped", reason
            return result
        print("Deploying {} ({})".format(result.name, result.url), flush=True)
        deployment = client.create_deployment(app["id"], force_build)
        result.deployment_id = deployment["id"]
        print("{}: deployment {}".format(result.name, result.deployment_id), flush=True)
        client.wait_for_deployment(app["id"], result.deployment_id, timeout)
        result.status = "Succeeded"
        result.detail = "Deployment is ACTIVE"
    except DeploymentError as error:
        result.detail = str(error)
    print("{}: {} {}".format(result.name, result.status, result.detail), flush=True)
    return result


def rollout(client, targets, results, args):
    if args.canary:
        canaries = [app for app in targets if app["spec"]["name"] == args.canary]
        if not canaries:
            raise DeploymentError("Canary must name an eligible app, including the mittab- prefix")
        targets = canaries + [app for app in targets if app not in canaries]

    planned = [Result(app["id"], app["spec"]["name"], "Not started") for app in targets]
    offset = len(results)
    results.extend(planned)
    if not targets:
        raise DeploymentError("No eligible tournament apps found")
    for index, result in enumerate(planned):
        result.detail = "Canary" if index == 0 else "After canary succeeds"
        print("Target: {} ({}) - {}".format(result.name, result.app_id, result.detail), flush=True)
    if not args.execute:
        for result in planned:
            result.status = "Would deploy"
        print("Preview only. No deployments were created.", flush=True)
        return 0

    def deploy(app):
        return deploy_one(client, app, args.branch, args.include_tests, args.force_build, args.timeout)

    # The first app must reach ACTIVE before any other deployment is created.
    results[offset] = deploy(targets[0])
    if results[offset].status != "Succeeded":
        return 1

    for start in range(1, len(targets), args.batch_size):
        batch = targets[start:start + args.batch_size]
        with ThreadPoolExecutor(max_workers=args.batch_size) as executor:
            batch_results = list(executor.map(deploy, batch))
        results[offset + start:offset + start + len(batch_results)] = batch_results
        # Finish the current batch, then stop if any app failed or changed.
        if any(result.status != "Succeeded" for result in batch_results):
            return 1
    return 0


def write_summary(results, error=""):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = ["## MITTab redeployment", ""]
    if error:
        lines.extend([cell(error), ""])
    lines.extend(["| Tournament | Result | Details | Deployment |", "| --- | --- | --- | --- |"])
    for result in results:
        lines.append("| [{}]({}) | {} | {} | {} |".format(
            cell(result.name), result.url, cell(result.status), cell(result.detail), cell(result.deployment_id)
        ))
    summary = "\n".join(lines) + "\n"
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as output:
            output.write(summary)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=("master", "discord", "all"), default="master")
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Deploy; otherwise only preview targets")
    parser.add_argument("--canary", default="", help="Full app name to deploy first; defaults to first by name")
    parser.add_argument("--batch-size", type=positive_int, default=3)
    parser.add_argument("--timeout", type=positive_int, default=1800, help="Seconds to wait per deployment")
    parser.add_argument("--force-build", action="store_true", help="Disable reuse of previous builds")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    results, error, exit_code = [], "", 1
    try:
        token = os.environ.get("DIGITALOCEAN_TOKEN")
        if not token:
            raise DeploymentError("Set DIGITALOCEAN_TOKEN before running (including previews)")
        client = DigitalOcean(token)
        targets, skipped = select_apps(client.list_apps(), args.branch, args.include_tests)
        results.extend(skipped)
        exit_code = rollout(client, targets, results, args)
    except DeploymentError as exception:
        error = str(exception)
    finally:
        write_summary(results, error)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
