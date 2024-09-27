#!/usr/bin/env python3
"""Unit tests for dependabot_report.py."""
import os

import pytest

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
