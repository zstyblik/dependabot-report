#!/usr/bin/env python3
"""Unit tests for dependabot_report.py."""
import os
from unittest.mock import call
from unittest.mock import MagicMock  # noqa: I100
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from github import GithubException

import dependabot_report  # noqa: I100,I202

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))


@pytest.mark.parametrize(
    "count,expected_log_level",
    [
        (0, 40),
        (1, 30),
        (2, 20),
        (3, 10),
        (4, 10),
        (5, 10),
        (50, 10),
    ],
)
def test_calc_log_level(count, expected_log_level):
    """Test that calc_log_level() works as expected."""
    result = dependabot_report.calc_log_level(count)
    assert result == expected_log_level


def test_get_github_token_env(monkeypatch):
    """Test reading GH token from ENV in get_github_token()."""
    input_data = "env:PYTEST_TOKEN"
    expected = "pytest-pytest"
    monkeypatch.setenv("PYTEST_TOKEN", expected)
    result = dependabot_report.get_github_token(input_data)
    assert result == expected


def test_get_github_token_env_not_set():
    """Test get_github_token() when target ENV variable isn't set."""
    input_data = "env:PYTEST_TOKEN"
    expected = ""
    result = dependabot_report.get_github_token(input_data)
    assert result == expected


def test_get_github_token_file():
    """Test reading GH token from ENV in get_github_token()."""
    token_fname = os.path.join(SCRIPT_PATH, "files", "github_token.txt")
    input_data = "file:{:s}".format(token_fname)
    expected = "hello_from_pytest"
    result = dependabot_report.get_github_token(input_data)
    assert result == expected


@pytest.mark.parametrize(
    "input_data,expected_exc_msg",
    [
        ("foo", "GitHub Token Path is empty"),
        ("foo:", "GitHub Token Path is empty"),
        (":foo", "GitHub Token Provider is empty"),
        ("foo:bar:lar:mar", "GitHub Token Provider 'foo' is not supported"),
        (
            "file:/path/does/not/exist",
            (
                "Error reading GitHub Token from '/path/does/not/exist': "
                "No such file or directory"
            ),
        ),
    ],
)
def test_get_github_token_exceptions(input_data, expected_exc_msg):
    """Test exceptions in get_github_token()."""
    with pytest.raises(dependabot_report.GitHubProviderException) as excinfo:
        dependabot_report.get_github_token(input_data)

    assert excinfo.value.message == expected_exc_msg


@patch("dependabot_report.github.Github")
def test_get_dependabot_data_no_filter(mock_github):
    """Test get_dependabot_data() when no filtering is set.

    This is rather sad. So much mockery!
    """
    # Mocked Alerts
    mock_alert1 = Mock()
    mock_alert1.number = 10

    mock_alert2 = Mock()
    mock_alert2.number = 21
    # Mocked Owners
    mock_owner1 = Mock(login="zstyblik1")
    mock_owner2 = Mock(login="zstyblik2")
    # Mocked Repositories
    mock_repo1 = MagicMock()
    mock_repo1.owner = mock_owner1
    mock_repo1.full_name = "dependabot-report1"
    mock_repo1.fork = False
    mock_repo1.html_url = "https://dbr1.example.com"
    mock_repo1.get_dependabot_alerts.return_value.__iter__.return_value = [
        mock_alert1,
        mock_alert2,
    ]

    mock_repo2 = MagicMock()
    mock_repo2.owner = mock_owner2
    mock_repo2.full_name = "dependabot-report2"
    mock_repo2.fork = True
    mock_repo2.html_url = "https://dbr2.example.com"
    mock_repo2.get_dependabot_alerts.return_value.__iter__.return_value = []
    # Disabled dependabot alerts
    mock_repo3 = MagicMock()
    mock_repo3.owner = mock_owner1
    mock_repo3.full_name = "dependabot-report3"
    mock_repo3.fork = False
    mock_repo3.html_url = "https://dbr3.example.com"
    mock_repo3.get_dependabot_alerts.return_value.__iter__.side_effect = [
        GithubException(status=403)
    ]

    mock_repos_iter = MagicMock()
    mock_repos_iter.__iter__.return_value = [mock_repo1, mock_repo2, mock_repo3]
    # Mocked User
    mock_guser = Mock()
    mock_guser.get_repos.return_value = mock_repos_iter

    mock_github.return_value.get_user.return_value = mock_guser
    #
    token = "pytest-token"
    repo_affiliation = "owner"
    exclude_gh_owner = []
    exclude_forks = False
    expected_guser_calls = [
        call.get_repos(
            affiliation=repo_affiliation, sort="full_name", direction="asc"
        ),
        call.get_repos().__iter__(),
    ]

    expected_ctx = {
        "namespaces": {
            "zstyblik1": {
                "owner": mock_owner1,
                "repos": {
                    "dependabot-report1": {
                        "alerts": {
                            mock_alert1.number: mock_alert1,
                            mock_alert2.number: mock_alert2,
                        },
                        "alerts_error": False,
                        "fork": False,
                        "html_url": "https://dbr1.example.com",
                        "html_filters": set(),
                    },
                    "dependabot-report3": {
                        "alerts": {},
                        "alerts_error": True,
                        "fork": False,
                        "html_filters": {
                            "github-repo-empty",
                            "github-repo-error",
                        },
                        "html_url": "https://dbr3.example.com",
                    },
                },
            },
            "zstyblik2": {
                "owner": mock_owner2,
                "repos": {
                    "dependabot-report2": {
                        "alerts": {},
                        "alerts_error": False,
                        "fork": True,
                        "html_url": "https://dbr2.example.com",
                        "html_filters": {
                            "github-repo-fork",
                            "github-repo-empty",
                        },
                    }
                },
            },
        },
        "report_mtime": 0,
        "timing_sec": "0",
    }

    ctx = dependabot_report.get_dependabot_data(
        token, repo_affiliation, exclude_gh_owner, exclude_forks
    )

    assert ctx == expected_ctx
    assert expected_guser_calls == mock_guser.mock_calls


@patch("dependabot_report.github.Github")
def test_get_dependabot_data_filter_owner(mock_github):
    """Test get_dependabot_data() with owner filter.

    This is rather sad. So much mockery!
    """
    # Mocked Alerts
    mock_alert1 = Mock()
    mock_alert1.number = 10

    mock_alert2 = Mock()
    mock_alert2.number = 21
    # Mocked Owners
    mock_owner1 = Mock(login="zstyblik1")
    mock_owner2 = Mock(login="zstyblik2")
    # Mocked Repositories
    mock_repo1 = MagicMock()
    mock_repo1.owner = mock_owner1
    mock_repo1.full_name = "dependabot-report1"
    mock_repo1.fork = False
    mock_repo1.html_url = "https://dbr1.example.com"
    mock_repo1.get_dependabot_alerts.return_value.__iter__.return_value = []

    mock_repo2 = MagicMock()
    mock_repo2.owner = mock_owner2
    mock_repo2.full_name = "dependabot-report2"
    mock_repo2.fork = True
    mock_repo2.html_url = "https://dbr2.example.com"
    mock_repo2.get_dependabot_alerts.return_value.__iter__.return_value = []

    mock_repos_iter = MagicMock()
    mock_repos_iter.__iter__.return_value = [mock_repo1, mock_repo2]
    # Mocked User
    mock_guser = Mock()
    mock_guser.get_repos.return_value = mock_repos_iter

    mock_github.return_value.get_user.return_value = mock_guser
    #
    token = "pytest-token"
    repo_affiliation = "owner"
    exclude_gh_owner = []
    exclude_forks = True

    expected_guser_calls = [
        call.get_repos(
            affiliation=repo_affiliation, sort="full_name", direction="asc"
        ),
        call.get_repos().__iter__(),
    ]

    expected_ctx = {
        "namespaces": {
            "zstyblik1": {
                "owner": mock_owner1,
                "repos": {
                    "dependabot-report1": {
                        "alerts": {},
                        "alerts_error": False,
                        "fork": False,
                        "html_url": "https://dbr1.example.com",
                        "html_filters": {"github-repo-empty"},
                    }
                },
            },
            "zstyblik2": {"owner": mock_owner2, "repos": {}},
        },
        "report_mtime": 0,
        "timing_sec": "0",
    }

    ctx = dependabot_report.get_dependabot_data(
        token, repo_affiliation, exclude_gh_owner, exclude_forks
    )

    assert ctx == expected_ctx
    assert expected_guser_calls == mock_guser.mock_calls


@patch("dependabot_report.github.Github")
def test_get_dependabot_data_filter_forks(mock_github):
    """Test get_dependabot_data() with fork filter.

    This is rather sad. So much mockery!
    """
    # Mocked Alerts
    mock_alert1 = Mock(number=10)
    mock_alert2 = Mock(number=21)
    # Mocked Owners
    mock_owner1 = Mock(login="zstyblik1")
    mock_owner2 = Mock(login="zstyblik2")
    # Mocked Repositories
    mock_repo1 = MagicMock()
    mock_repo1.owner = mock_owner1
    mock_repo1.full_name = "dependabot-report1"
    mock_repo1.fork = False
    mock_repo1.html_url = "https://dbr1.example.com"
    mock_repo1.get_dependabot_alerts.return_value.__iter__.return_value = [
        mock_alert1
    ]

    mock_repo2 = MagicMock()
    mock_repo2.owner = mock_owner2
    mock_repo2.full_name = "dependabot-report2"
    mock_repo2.fork = True
    mock_repo2.html_url = "https://dbr2.example.com"
    mock_repo2.get_dependabot_alerts.return_value.__iter__.return_value = [
        mock_alert2
    ]

    mock_repos_iter = MagicMock()
    mock_repos_iter.__iter__.return_value = [mock_repo1, mock_repo2]
    # Mocked User
    mock_guser = Mock()
    mock_guser.get_repos.return_value = mock_repos_iter

    mock_github.return_value.get_user.return_value = mock_guser
    #
    token = "pytest-token"
    repo_affiliation = "organization_member"
    exclude_gh_owner = ["zstyblik2"]
    exclude_forks = False

    expected_guser_calls = [
        call.get_repos(
            affiliation=repo_affiliation, sort="full_name", direction="asc"
        ),
        call.get_repos().__iter__(),
    ]

    expected_ctx = {
        "namespaces": {
            "zstyblik1": {
                "owner": mock_owner1,
                "repos": {
                    "dependabot-report1": {
                        "alerts": {mock_alert1.number: mock_alert1},
                        "alerts_error": False,
                        "fork": False,
                        "html_url": "https://dbr1.example.com",
                        "html_filters": set(),
                    }
                },
            }
        },
        "report_mtime": 0,
        "timing_sec": "0",
    }

    ctx = dependabot_report.get_dependabot_data(
        token, repo_affiliation, exclude_gh_owner, exclude_forks
    )

    assert ctx == expected_ctx
    assert expected_guser_calls == mock_guser.mock_calls
