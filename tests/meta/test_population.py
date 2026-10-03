"""The two controls a guard proves its population with (#178)."""

import tomllib
from pathlib import Path

import pytest
from population import ROOT, BlindGuardError, git, searched, tracked


def test_a_parametrize_over_nothing_fails_rather_than_skips() -> None:
    # A population derived at collection (files on disk, recordings) that comes out empty would
    # otherwise be one skipped test, and the run stays green.
    pytest_options = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pytest_options["tool"]["pytest"]["ini_options"]["empty_parameter_set_mark"] == (
        "fail_at_collect"
    )


def test_a_verdict_over_a_population_is_its_findings() -> None:
    assert searched({}, of=3, what="modules") == {}
    assert searched(["x"], of=1, what="modules") == ["x"]


def test_a_verdict_over_no_population_is_refused_by_name() -> None:
    with pytest.raises(BlindGuardError, match=r"^judged no modules: "):
        searched([], of=0, what="modules")


def test_git_lists_this_file_and_its_neighbours() -> None:
    meta = tracked(ROOT / "tests/meta", ".py")
    assert Path(__file__) in meta
    assert ROOT / "tests/meta/population.py" in meta
    assert all(  # runtime population: the files git listed
        path.suffix == ".py" and ROOT / "tests/meta" in path.parents for path in meta
    )


def test_git_lists_a_new_file_and_not_an_ignored_one(tmp_path: Path) -> None:
    git("init", "-q", cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    for name in ("new.py", "ignored.py", "note.md", "sub/deep.py"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert tracked(tmp_path, ".py", root=tmp_path) == [
        tmp_path / "new.py",
        tmp_path / "sub/deep.py",
    ]


def test_no_git_on_the_path_is_refused_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    with pytest.raises(BlindGuardError, match=r"^git is not on the path: "):
        tracked(ROOT / "tests/meta", ".py")
