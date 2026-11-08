"""The release-cut check (#400, shyden-labs/repo-template#86): `main` takes only a frozen
`release/*` cut, by merge commit, and is not strict, so this check proves what strict did: that
what lands on `main` is exactly what CI tested on `develop`. Ported from the template's
`scripts/release-cut.ts` and its tests (docs/release-cut.md there).

A unit test starts no process (#286): git is stood in, answering each call by its arguments, and
GitHub's status endpoint is stood in too."""

import io
import json
import re
import runpy
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest
import release_cut
from release_cut import (
    MERGE_REF,
    RELEASE_CUT,
    Facts,
    MainCommit,
    ReleaseCutError,
    Status,
    audit,
    gather_facts,
    main,
    parse_parents,
    parse_remote_head,
    run,
    status_for,
)
from script_imports import imported_modules

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/release_cut.py"
FAKE_GIT = "/stood-in/bin/git"


def exactly(text: str) -> str:
    """A ``match=`` pattern for exactly *text*."""
    return f"^{re.escape(text)}$"


HEAD = "a" * 40
MERGE = "b" * 40
OLD_MAIN = "c" * 40
OLD_CUT = "d" * 40
STRAY = "e" * 40
TREE = "f" * 40
PR_MERGE = "9" * 40
DEVELOP_TIP = "8" * 40
REF = "release/2026-11-08"

# A second cut after one release merge: every fact as it should be.
GOOD = Facts(
    head_ref=REF,
    head_sha=HEAD,
    origin_head_sha=HEAD,
    head_on_develop=True,
    merge_parents=(MERGE, HEAD),
    merge_tree=TREE,
    head_tree=TREE,
    main_commits=(MainCommit(MERGE, (OLD_MAIN, OLD_CUT), second_parent_on_develop=True),),
)


# --- audit ------------------------------------------------------------------------------------


def test_the_first_cut_passes_when_main_holds_nothing_develop_lacks() -> None:
    assert audit(replace(GOOD, main_commits=())) == []


def test_a_second_cut_after_one_release_merge_passes() -> None:
    assert audit(GOOD) == []


def test_a_head_branch_that_is_not_a_release_branch_is_refused() -> None:
    assert audit(replace(GOOD, head_ref="feature/x")) == [
        "the head branch is feature/x, not a release/ branch"
    ]


def test_a_bare_release_slash_is_refused() -> None:
    assert audit(replace(GOOD, head_ref="release/")) == [
        "the head branch is release/, not a release/ branch"
    ]


def test_a_head_branch_origin_does_not_hold_is_refused() -> None:
    assert audit(replace(GOOD, origin_head_sha=None)) == [f"origin holds no branch {REF}"]


def test_a_head_branch_origin_holds_at_another_commit_is_refused() -> None:
    assert audit(replace(GOOD, origin_head_sha=STRAY)) == [
        f"origin's {REF} is at {STRAY}, not the head {HEAD}"
    ]


def test_a_head_that_is_not_on_develop_is_refused() -> None:
    assert audit(replace(GOOD, head_on_develop=False)) == [
        f"the head {HEAD} is not on origin/develop"
    ]


def test_a_merge_that_is_not_githubs_merge_of_the_head_is_refused() -> None:
    assert audit(replace(GOOD, merge_parents=(MERGE, STRAY))) == [
        (
            f"the checked-out commit is not GitHub's merge of the head {HEAD} into main "
            f"(its parents: {MERGE} {STRAY})"
        )
    ]


def test_a_merge_with_one_parent_is_refused() -> None:
    assert audit(replace(GOOD, merge_parents=(HEAD,))) == [
        (
            f"the checked-out commit is not GitHub's merge of the head {HEAD} into main "
            f"(its parents: {HEAD})"
        )
    ]


def test_a_merge_whose_tree_is_not_the_heads_is_refused() -> None:
    assert audit(replace(GOOD, merge_tree=STRAY)) == [
        f"the merge would land tree {STRAY}, not the head's tree {TREE}"
    ]


def test_a_main_holding_a_direct_commit_is_refused() -> None:
    commits = (MainCommit(STRAY, (OLD_MAIN,), second_parent_on_develop=None),)
    assert audit(replace(GOOD, main_commits=commits)) == [
        f"main holds {STRAY}, which has 1 parent, not a merge of a release cut"
    ]


def test_a_main_holding_a_root_commit_is_refused() -> None:
    commits = (MainCommit(STRAY, (), second_parent_on_develop=None),)
    assert audit(replace(GOOD, main_commits=commits)) == [
        f"main holds {STRAY}, which has 0 parents, not a merge of a release cut"
    ]


def test_a_main_holding_an_octopus_merge_is_refused() -> None:
    commits = (MainCommit(STRAY, (OLD_MAIN, OLD_CUT, MERGE), second_parent_on_develop=None),)
    assert audit(replace(GOOD, main_commits=commits)) == [
        f"main holds {STRAY}, which has 3 parents, not a merge of a release cut"
    ]


def test_a_main_holding_a_merge_whose_second_parent_is_not_on_develop_is_refused() -> None:
    commits = (MainCommit(MERGE, (OLD_MAIN, STRAY), second_parent_on_develop=False),)
    assert audit(replace(GOOD, main_commits=commits)) == [
        f"main holds the merge {MERGE}, whose second parent {STRAY} is not on origin/develop"
    ]


def test_every_failure_is_named_in_the_order_it_is_judged() -> None:
    facts = Facts(
        head_ref="hotfix",
        head_sha=HEAD,
        origin_head_sha=None,
        head_on_develop=False,
        merge_parents=(),
        merge_tree=STRAY,
        head_tree=TREE,
        main_commits=(MainCommit(STRAY, (OLD_MAIN,), second_parent_on_develop=None),),
    )
    assert audit(facts) == [
        "the head branch is hotfix, not a release/ branch",
        "origin holds no branch hotfix",
        f"the head {HEAD} is not on origin/develop",
        (
            f"the checked-out commit is not GitHub's merge of the head {HEAD} into main "
            "(its parents: )"
        ),
        f"the merge would land tree {STRAY}, not the head's tree {TREE}",
        f"main holds {STRAY}, which has 1 parent, not a merge of a release cut",
    ]


# --- parse_parents ----------------------------------------------------------------------------


def test_parents_are_read_for_each_commit_in_order() -> None:
    text = f"{MERGE} {OLD_MAIN} {OLD_CUT}\n{STRAY} {OLD_MAIN}\n"
    assert parse_parents(text) == [(MERGE, (OLD_MAIN, OLD_CUT)), (STRAY, (OLD_MAIN,))]


def test_an_empty_answer_has_no_commits() -> None:
    assert parse_parents("") == []


def test_a_root_commit_has_no_parents() -> None:
    assert parse_parents(f"{STRAY}\n") == [(STRAY, ())]


def test_a_line_that_is_not_shas_is_unreadable() -> None:
    with pytest.raises(ReleaseCutError, match=exactly("unreadable rev-list line: not a sha")):
        parse_parents("not a sha\n")


def test_an_empty_line_inside_the_answer_is_unreadable() -> None:
    with pytest.raises(ReleaseCutError, match=exactly("unreadable rev-list line: ")):
        parse_parents(f"{MERGE} {OLD_MAIN}\n\n{STRAY}\n")


# --- parse_remote_head ------------------------------------------------------------------------

QUESTION = "ls-remote origin refs/heads/develop refs/heads/release/x"
DEVELOP_LINE = f"{DEVELOP_TIP}\trefs/heads/develop\n"


def test_the_commit_origin_holds_the_branch_at_is_read() -> None:
    text = DEVELOP_LINE + f"{HEAD}\trefs/heads/release/x\n"
    assert parse_remote_head(text, "refs/heads/release/x", QUESTION) == HEAD


def test_a_branch_origin_does_not_name_is_absent() -> None:
    assert parse_remote_head(DEVELOP_LINE, "refs/heads/release/x", QUESTION) is None


def test_a_branch_whose_name_only_ends_in_the_ref_is_not_it() -> None:
    text = DEVELOP_LINE + f"{STRAY}\trefs/heads/old/release/x\n"
    assert parse_remote_head(text, "refs/heads/release/x", QUESTION) is None


def test_an_answer_naming_no_develop_cannot_be_read() -> None:
    with pytest.raises(
        ReleaseCutError,
        match=exactly(f"git {QUESTION} named no refs/heads/develop, so its answer cannot be read"),
    ):
        parse_remote_head("", "refs/heads/release/x", QUESTION)


def test_a_branch_named_twice_fails_naming_it() -> None:
    text = DEVELOP_LINE + f"{HEAD}\trefs/heads/release/x\n{STRAY}\trefs/heads/release/x\n"
    with pytest.raises(
        ReleaseCutError, match=exactly(f"git {QUESTION} named refs/heads/release/x twice")
    ):
        parse_remote_head(text, "refs/heads/release/x", QUESTION)


def test_an_unreadable_ls_remote_line_fails_naming_it() -> None:
    with pytest.raises(ReleaseCutError, match=exactly("unreadable ls-remote line: garbage")):
        parse_remote_head("garbage\n", "refs/heads/release/x", QUESTION)


# --- gather_facts -----------------------------------------------------------------------------


@dataclass
class AnsweringGit:
    """``subprocess.run`` for the check: answers each git call by its arguments, refuses any call
    no case answered, and keeps each call."""

    answers: dict[tuple[str, ...], tuple[int, str, str]]
    calls: list[tuple[list[str], dict[str, object]]] = field(default_factory=list)

    def run(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), kwargs))
        question = tuple(args[1:])
        if args[0] != FAKE_GIT or question not in self.answers:
            msg = f"no case answers {args}"
            raise AssertionError(msg)
        code, out, err = self.answers[question]
        return subprocess.CompletedProcess(args, code, out, err)

    def asked(self) -> list[tuple[str, ...]]:
        return [tuple(args[1:]) for args, _ in self.calls]


FETCH = ("fetch", "--no-tags", "origin", f"+refs/pull/7/merge:{MERGE_REF}")
LS_REMOTE = ("ls-remote", "origin", "refs/heads/develop", f"refs/heads/{REF}")
HEAD_ON_DEVELOP = ("merge-base", "--is-ancestor", HEAD, "origin/develop")
MERGE_PARENTS = ("rev-list", "--parents", "-n", "1", MERGE_REF)
MERGE_TREE = ("rev-parse", f"{MERGE_REF}^{{tree}}")
HEAD_TREE = ("rev-parse", f"{HEAD}^{{tree}}")
BEYOND = ("rev-list", "--parents", "origin/develop..origin/main")
CUT_ON_DEVELOP = ("merge-base", "--is-ancestor", OLD_CUT, "origin/develop")


def good_answers() -> dict[tuple[str, ...], tuple[int, str, str]]:
    return {
        FETCH: (0, "", ""),
        LS_REMOTE: (0, DEVELOP_LINE + f"{HEAD}\trefs/heads/{REF}\n", ""),
        HEAD_ON_DEVELOP: (0, "", ""),
        MERGE_PARENTS: (0, f"{PR_MERGE} {MERGE} {HEAD}\n", ""),
        MERGE_TREE: (0, f"{TREE}\n", ""),
        HEAD_TREE: (0, f"{TREE}\n", ""),
        BEYOND: (0, f"{MERGE} {OLD_MAIN} {OLD_CUT}\n", ""),
        CUT_ON_DEVELOP: (0, "", ""),
    }


def stand_in_git(
    monkeypatch: pytest.MonkeyPatch, answers: dict[tuple[str, ...], tuple[int, str, str]]
) -> AnsweringGit:
    git = AnsweringGit(answers)
    monkeypatch.setattr(subprocess, "run", git.run)
    monkeypatch.setattr(shutil, "which", lambda name: FAKE_GIT if name == "git" else None)
    return git


def test_the_stood_in_git_refuses_a_question_no_case_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand_in_git(monkeypatch, {})
    with pytest.raises(AssertionError, match="no case answers"):
        gather_facts(REF, HEAD, 7)


def test_the_merge_ref_is_fetched_first_then_each_question_is_asked_once_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = stand_in_git(monkeypatch, good_answers())
    assert gather_facts(REF, HEAD, 7) == GOOD
    assert git.asked() == [
        FETCH,
        LS_REMOTE,
        HEAD_ON_DEVELOP,
        MERGE_PARENTS,
        MERGE_TREE,
        HEAD_TREE,
        BEYOND,
        CUT_ON_DEVELOP,
    ]


def test_git_runs_with_its_output_read_as_text_and_nothing_on_its_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = stand_in_git(monkeypatch, good_answers())
    gather_facts(REF, HEAD, 7)
    assert {repr(kwargs) for _, kwargs in git.calls} == {
        repr(
            {
                "capture_output": True,
                "text": True,
                "check": False,
                "stdin": subprocess.DEVNULL,
            }
        )
    }


def test_the_head_branch_is_absent_when_origin_names_develop_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[LS_REMOTE] = (0, DEVELOP_LINE, "")
    stand_in_git(monkeypatch, answers)
    assert gather_facts(REF, HEAD, 7).origin_head_sha is None


def test_status_1_from_is_ancestor_reads_as_not_on_develop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[HEAD_ON_DEVELOP] = (1, "", "")
    stand_in_git(monkeypatch, answers)
    assert gather_facts(REF, HEAD, 7).head_on_develop is False


def test_an_is_ancestor_error_fails_naming_the_question_rather_than_reading_as_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[HEAD_ON_DEVELOP] = (128, "", "fatal: Not a valid commit name\n")
    stand_in_git(monkeypatch, answers)
    with pytest.raises(
        ReleaseCutError,
        match=exactly(
            f"git merge-base --is-ancestor {HEAD} origin/develop failed: "
            "fatal: Not a valid commit name"
        ),
    ):
        gather_facts(REF, HEAD, 7)


def test_a_merge_ref_that_cannot_be_fetched_fails_asking_nothing_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = stand_in_git(monkeypatch, {FETCH: (128, "", "fatal: couldn't find remote ref\n")})
    with pytest.raises(
        ReleaseCutError,
        match=exactly(f"git {' '.join(FETCH)} failed: fatal: couldn't find remote ref"),
    ):
        gather_facts(REF, HEAD, 7)
    assert git.asked() == [FETCH]


def test_only_two_parent_commits_have_their_second_parent_asked_about(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[BEYOND] = (0, f"{MERGE} {OLD_MAIN} {OLD_CUT}\n{STRAY} {OLD_MAIN}\n", "")
    git = stand_in_git(monkeypatch, answers)
    assert gather_facts(REF, HEAD, 7).main_commits == (
        MainCommit(MERGE, (OLD_MAIN, OLD_CUT), second_parent_on_develop=True),
        MainCommit(STRAY, (OLD_MAIN,), second_parent_on_develop=None),
    )
    assert git.asked().count(CUT_ON_DEVELOP) == 1


def test_no_merge_commit_named_reads_as_no_parents_so_the_merge_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[MERGE_PARENTS] = (0, "", "")
    stand_in_git(monkeypatch, answers)
    assert gather_facts(REF, HEAD, 7).merge_parents == ()


def test_no_git_on_the_path_fails_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ReleaseCutError, match=exactly("release-cut needs git on the PATH")):
        gather_facts(REF, HEAD, 7)


# --- status_for -------------------------------------------------------------------------------


def test_a_release_cut_passes() -> None:
    assert status_for([]) == Status(
        "success", "a tested release cut: the merge lands the head's tree"
    )


def test_one_reason_is_named() -> None:
    assert status_for(["the head is not on origin/develop"]) == Status(
        "failure", "the head is not on origin/develop"
    )


def test_the_first_reason_is_named_with_how_many_more_the_log_holds() -> None:
    assert status_for(["first", "second", "third"]) == Status(
        "failure", "first (and 2 more in the log)"
    )


def test_a_reason_of_exactly_140_characters_is_kept_whole() -> None:
    assert status_for(["x" * 140]).description == "x" * 140


def test_a_long_reason_is_cut_to_140_characters_ending_in_an_ellipsis() -> None:
    description = status_for(["x" * 141]).description
    assert (len(description), description[-1]) == (140, "…")


# --- main -------------------------------------------------------------------------------------

ENV: Mapping[str, str] = {
    "GITHUB_TOKEN": "t0ken",
    "GITHUB_REPOSITORY": "ShydenMcM/steadyhand",
    "GITHUB_API_URL": "https://api.github.test",
    "GITHUB_SERVER_URL": "https://github.test",
    "GITHUB_RUN_ID": "42",
}
ARGS = ["ShydenMcM/steadyhand", REF, HEAD, "7"]


@dataclass
class StatusEndpoint:
    """``urlopen`` for GitHub's status endpoint: keeps each request and answers *code*."""

    code: int = 201
    requests: list[urllib.request.Request] = field(default_factory=list)

    def urlopen(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert timeout == 30
        self.requests.append(request)
        if self.code >= 300:
            raise urllib.error.HTTPError(request.full_url, self.code, "no", None, None)  # type: ignore[arg-type]
        return io.BytesIO(b"{}")

    def posted(self) -> list[dict[str, object]]:
        return [json.loads(request.data) for request in self.requests]  # type: ignore[arg-type]


def stand_in_github(monkeypatch: pytest.MonkeyPatch, code: int = 201) -> StatusEndpoint:
    endpoint = StatusEndpoint(code)
    monkeypatch.setattr(release_cut, "urlopen", endpoint.urlopen)
    return endpoint


def posted_status(state: str, description: str) -> dict[str, object]:
    return {
        "state": state,
        "description": description,
        "context": RELEASE_CUT,
        "target_url": "https://github.test/ShydenMcM/steadyhand/actions/runs/42",
    }


def test_a_release_cut_posts_success_says_what_it_judged_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stand_in_git(monkeypatch, good_answers())
    github = stand_in_github(monkeypatch)
    assert main(ARGS, ENV) == 0
    assert github.posted() == [
        posted_status("success", "a tested release cut: the merge lands the head's tree")
    ]
    assert capsys.readouterr().out == (
        f"release-cut: {REF} at {HEAD}; judged 1 commit(s) in origin/develop..origin/main; "
        "the merge lands the head's tree.\n"
    )


def test_the_status_is_posted_on_the_head_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in_git(monkeypatch, good_answers())
    github = stand_in_github(monkeypatch)
    main(ARGS, ENV)
    [request] = github.requests
    assert (request.full_url, request.get_method()) == (
        f"https://api.github.test/repos/ShydenMcM/steadyhand/statuses/{HEAD}",
        "POST",
    )
    assert request.headers == {
        "Authorization": "Bearer t0ken",
        "Accept": "application/vnd.github+json",
        "X-github-api-version": "2022-11-28",
        "Content-type": "application/json",
    }


def test_a_merge_that_is_not_a_release_cut_posts_failure_and_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = good_answers()
    answers[HEAD_ON_DEVELOP] = (1, "", "")
    stand_in_git(monkeypatch, answers)
    github = stand_in_github(monkeypatch)
    with pytest.raises(
        ReleaseCutError,
        match=exactly(
            f"release-cut refuses this merge:\n  the head {HEAD} is not on origin/develop"
        ),
    ):
        main(ARGS, ENV)
    assert github.posted() == [
        posted_status("failure", f"the head {HEAD} is not on origin/develop")
    ]


def test_git_that_cannot_answer_posts_an_error_then_fails_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand_in_git(monkeypatch, {FETCH: (128, "", "fatal: no merge ref\n")})
    github = stand_in_github(monkeypatch)
    with pytest.raises(ReleaseCutError, match="fatal: no merge ref"):
        main(ARGS, ENV)
    assert github.posted() == [
        posted_status(
            "error", f"could not judge: git {' '.join(FETCH)} failed: fatal: no merge ref"
        )
    ]


def test_a_status_github_refuses_fails_naming_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in_git(monkeypatch, good_answers())
    stand_in_github(monkeypatch, code=403)
    with pytest.raises(
        ReleaseCutError,
        match=exactly(
            f"POST https://api.github.test/repos/ShydenMcM/steadyhand/statuses/{HEAD} answered "
            "403; the pull request has no release-cut status"
        ),
    ):
        main(ARGS, ENV)


@pytest.mark.parametrize(
    "args",
    [
        ARGS[:3],
        [*ARGS, "extra"],
        [ARGS[0], REF, "A" * 40, "7"],
        [ARGS[0], REF, HEAD[:39], "7"],
        [ARGS[0], REF, HEAD, "0"],
        [ARGS[0], REF, HEAD, "07"],
        [ARGS[0], REF, HEAD, "seven"],
    ],
    ids=["three", "five", "upper-hex", "short-sha", "zero", "leading-zero", "not-a-number"],
)
def test_arguments_other_than_the_four_are_refused_with_the_usage(args: list[str]) -> None:
    with pytest.raises(
        ReleaseCutError,
        match=exactly(
            "usage: release_cut.py <head repository> <head ref> <40-hex head sha> "
            "<pull request number>"
        ),
    ):
        main(args, ENV)


@pytest.mark.parametrize(
    "repository", ["someone/steadyhand", "ShydenMcM/Steadyhand", "ShydenMcM/steadyhand-fork", ""]
)
def test_a_pull_request_from_another_repository_posts_nothing(
    monkeypatch: pytest.MonkeyPatch, repository: str
) -> None:
    git = stand_in_git(monkeypatch, good_answers())
    github = stand_in_github(monkeypatch)
    with pytest.raises(
        ReleaseCutError,
        match=exactly(
            f"release-cut posts nothing for a pull request from {json.dumps(repository)}: a "
            "release cut comes from this repository's own release/ branch, not a fork"
        ),
    ):
        main([repository, REF, HEAD, "7"], ENV)
    assert (git.calls, github.requests) == ([], [])


@pytest.mark.parametrize("name", list(ENV))
def test_a_missing_actions_variable_is_refused_asking_git_and_github_nothing(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    git = stand_in_git(monkeypatch, good_answers())
    github = stand_in_github(monkeypatch)
    env = {key: value for key, value in ENV.items() if key != name}
    with pytest.raises(
        ReleaseCutError, match=exactly(f"release-cut needs {name}, which GitHub Actions sets")
    ):
        main(ARGS, env)
    assert (git.calls, github.requests) == ([], [])


# --- the entry point --------------------------------------------------------------------------


def test_a_refusal_is_printed_on_stderr_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = good_answers()
    answers[HEAD_ON_DEVELOP] = (1, "", "")
    stand_in_git(monkeypatch, answers)
    stand_in_github(monkeypatch)
    assert run(ARGS, ENV) == 1
    assert capsys.readouterr().err == (
        f"release-cut refuses this merge:\n  the head {HEAD} is not on origin/develop\n"
    )


def test_a_release_cut_exits_0_through_run(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in_git(monkeypatch, good_answers())
    stand_in_github(monkeypatch)
    assert run(ARGS, ENV) == 0


def test_the_script_run_directly_judges_its_arguments_and_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *ARGS])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 1
    assert capsys.readouterr().err == "release-cut needs GITHUB_TOKEN, which GitHub Actions sets\n"


def test_the_script_imports_the_standard_library_alone() -> None:
    assert imported_modules(SCRIPT) <= set(sys.stdlib_module_names)


def test_an_api_address_that_is_not_https_is_refused_posting_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand_in_git(monkeypatch, good_answers())
    github = stand_in_github(monkeypatch)
    env = {**ENV, "GITHUB_API_URL": "file:///etc"}
    with pytest.raises(
        ReleaseCutError,
        match=exactly("release-cut posts only to an https:// GITHUB_API_URL, not file:///etc"),
    ):
        main(ARGS, env)
    assert github.requests == []
