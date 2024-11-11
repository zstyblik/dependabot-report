#!/usr/bin/env python3
"""Fetch GitHub's dependabot alerts in 'open' state and generate HTML report.

MIT License

Copyright (c) 2024 Zdenek Styblik

See LICENSE for details.
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from datetime import timezone

import github
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import select_autoescape

from lib.cisa import CWE_CISA_KEV_2023
from lib.owasp import CWE_OWASP_2021

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_FNAME = os.path.join(
    SCRIPT_PATH, "templates", "dependabot_report.html"
)


class GitHubProviderException(Exception):
    """Custom exception in order to signal problem with GH Provider parsing."""

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args)
        self.message = kwargs.get("message")


def calc_log_level(count: int) -> int:
    """Return logging log level as int based on count."""
    log_level = 40 - max(count, 0) * 10
    log_level = max(log_level, 10)
    return log_level


def get_github_token(input_data: str) -> str:
    """Return GH Token parsed out of input_data.

    :raises GitHubProviderException: if there is an error.
    """
    provider = input_data.split(":")[0]
    provider = provider.lower()
    token_path = ":".join(input_data.split(":")[1:])
    if not provider:
        raise GitHubProviderException(message="GitHub Token Provider is empty")

    if not token_path:
        raise GitHubProviderException(message="GitHub Token Path is empty")

    # NOTE(zstyblik): in case of eg. AWS SSM, branch these off into functions.
    if provider == "file":
        try:
            with open(token_path, mode="r", encoding="utf-8") as fhandle:
                token = fhandle.read()
        except OSError as exc:
            message = "Error reading GitHub Token from '{:s}': {}".format(
                token_path, exc.strerror
            )
            raise GitHubProviderException(message=message) from exc

    elif provider == "env":
        token = os.environ.get(token_path, "")
    else:
        raise GitHubProviderException(
            message="GitHub Token Provider '{}' is not supported".format(
                provider
            )
        )

    return token.strip()


def get_dependabot_data(
    token, repo_affiliation, exclude_github_owner, exclude_forks
):
    """Get data from GitHub and return it as context(dict) for jinja2.

    * Auth
    * Get repos
    * Get dependabot alerts for repos
    * Transform and return as ctx(dict)
    """
    auth = github.Auth.Token(token)
    ghub = github.Github(auth=auth)
    guser = ghub.get_user()
    logging.info(
        "Authentication to GitHub successful - authenticated as '%s'.",
        guser.login,
    )
    context = {
        "namespaces": {},
        "report_mtime": 0,
        "timing_sec": "0",
    }
    # NOTE(zstyblik): we want only repos user has access to, not the whole GH!
    repos = guser.get_repos(
        affiliation=repo_affiliation, sort="full_name", direction="asc"
    )
    for repo in repos:
        namespace = repo.owner.login
        if exclude_github_owner and namespace in exclude_github_owner:
            logging.debug("Skip '%s' based on GitHub owner filter.", namespace)
            continue

        if namespace not in context["namespaces"]:
            context["namespaces"][namespace] = {
                "owner": repo.owner,
                "repos": {},
            }

        if exclude_forks is True and repo.fork is True:
            logging.debug(
                "Skip repository '%s' because it's a fork.", repo.full_name
            )
            continue

        repo_detail = {
            "alerts": {},
            "alerts_error": False,
            "alerts_stats": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "fork": repo.fork,
            "html_url": repo.html_url,
            "html_filters": set(),
        }
        try:
            dependabot_alerts = repo.get_dependabot_alerts(state="open")
            for alert in dependabot_alerts:
                repo_detail["alerts"][alert.number] = alert
                stats_key = str(alert.security_advisory.severity).lower()
                repo_detail["alerts_stats"][stats_key] += 1
        except github.GithubException as exception:
            if exception.status == 403:
                # NOTE(zstyblik): 403 most likely means that dependabot
                # is disabled.
                repo_detail["alerts_error"] = True
                repo_detail["html_filters"].add("github-repo-error")
            else:
                raise

        if not repo_detail["alerts"]:
            repo_detail["html_filters"].add("github-repo-empty")

        if repo_detail["fork"]:
            repo_detail["html_filters"].add("github-repo-fork")

        context["namespaces"][namespace]["repos"][repo.full_name] = repo_detail

    return context


def has_cisa_cwe(alert):
    """Check whether alert's CWE are in CISA KEV lookup table."""
    if not alert.security_advisory:
        return False

    if not alert.security_advisory.cwes:
        return False

    for cwe in alert.security_advisory.cwes:
        cwe_id = str(cwe.cwe_id).upper()
        if cwe_id in CWE_CISA_KEV_2023:
            return True

    return False


def has_owasp_cwe(alert):
    """Check whether alert's CWE are in OWASP lookup table."""
    if not alert.security_advisory:
        return False

    if not alert.security_advisory.cwes:
        return False

    for cwe in alert.security_advisory.cwes:
        cwe_id = str(cwe.cwe_id).upper()
        if cwe_id in CWE_OWASP_2021:
            return True

    return False


def main():
    """Initialize, fetch data from GH and render HTML report."""
    timer_start = time.perf_counter()
    args = parse_args()
    logging.basicConfig(level=args.log_level, stream=sys.stdout)

    try:
        token = get_github_token(args.github_token_provider)
    except GitHubProviderException as exception:
        logging.error("%s", exception.message)
        sys.exit(1)

    context = get_dependabot_data(
        token,
        args.repo_affiliation,
        args.exclude_github_owner,
        args.exclude_forks,
    )
    dt_now = datetime.now(timezone.utc)
    context["report_mtime"] = dt_now.strftime("%Y-%m-%d %H:%M:%S%z")
    context["timing_sec"] = "{:.2f}".format(time.perf_counter() - timer_start)
    render_template(context, args.template_fname, args.output_file)


def parse_args() -> argparse.Namespace:
    """Return parsed CLI args."""
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument(
        "--github-token-provider",
        required=True,
        type=str,
        help=(
            "Provider which will provide GitHub token. "
            "Supported providers are 'file' or 'env'. "
            "Example usage: %(prog)s --github-token-provider 'file:token.txt'"
        ),
    )
    parser.add_argument(
        "--output-file",
        required=True,
        type=argparse.FileType("w", encoding="utf-8"),
        help="Write HTML report into given file.",
    )
    parser.add_argument(
        "--exclude-github-owner",
        action="append",
        help="Exclude repositories owned by given owner.",
    )
    parser.add_argument(
        "--exclude-forks",
        action="store_true",
        default=False,
        help=(
            "Exclude repositories which are not sources as forks don't "
            "receive security alerts."
        ),
    )
    parser.add_argument(
        "--include-repo-owner",
        action="store_const",
        const="owner",
        default="",
        help="Include repositories that are owned by the authenticated user.",
    )
    parser.add_argument(
        "--include-repo-collaborator",
        action="store_const",
        const="collaborator",
        default="",
        help=(
            "Include repositories that the user has been added to as "
            "a collaborator."
        ),
    )
    parser.add_argument(
        "--include-repo-org-member",
        action="store_const",
        const="organization_member",
        default="",
        help=(
            "Include repositories that the user has access to through being "
            "a member of an organization."
        ),
    )
    parser.add_argument(
        "--template-fname",
        default=TEMPLATE_FNAME,
        type=str,
        help="Path and filename of jinja2 template to use.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase log level verbosity. Can be passed multiple times.",
    )
    args = parser.parse_args()
    args.log_level = calc_log_level(args.verbose)

    if (
        not args.include_repo_owner
        and not args.include_repo_collaborator
        and not args.include_repo_org_member
    ):
        message = (
            "at least one of --include-repo-owner, "
            "--include-repo-collaborator or --include-repo-org-member "
            "must be given"
        )
        parser.error(message)

    args.repo_affiliation = ",".join(
        [
            args.include_repo_owner,
            args.include_repo_collaborator,
            args.include_repo_org_member,
        ]
    ).strip(",")
    return args


def render_template(context, template_fname, fhandle):
    """Render jinja2 template and write it into fhandle."""
    base_path = os.path.dirname(template_fname)
    logging.debug("Template base path: '%s'.", base_path)
    filename = os.path.basename(template_fname)
    logging.debug("Template file name: '%s'.", filename)
    jinja_env = Environment(
        loader=FileSystemLoader(base_path),
        autoescape=select_autoescape(),
    )
    jinja_env.tests["has_cisa_cwe"] = has_cisa_cwe
    jinja_env.tests["has_owasp_cwe"] = has_owasp_cwe
    template = jinja_env.get_template(filename)
    fhandle.write(template.render(context))


if __name__ == "__main__":
    main()
