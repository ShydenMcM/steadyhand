"""The one reading of ``ci.yml`` the workflow tests share (#285)."""

import pytest
import yaml
from ci_workflow import NoLibyamlError, ci, parse


def test_the_workflow_is_read_once_and_shared() -> None:
    assert ci() is ci()
    assert "jobs" in ci()


def test_on_is_read_as_yaml_1_1_reads_it_as_the_safe_loader_did() -> None:
    text = "on:\n  push: {}\nname: ci\n"
    assert parse(text) == yaml.safe_load(text) == {True: {"push": {}}, "name": "ci"}


def test_a_pyyaml_without_libyaml_is_refused_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(yaml, "CSafeLoader")
    with pytest.raises(NoLibyamlError, match="PyYAML has no CSafeLoader"):
        parse("name: ci\n")
