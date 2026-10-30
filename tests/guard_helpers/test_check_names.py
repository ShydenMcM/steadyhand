"""The check-name guard's reader, each seen finding a plant of every form it must recognise (#444).

The guard (``tests/guards/test_no_name_clash.py``) runs it over the repository's workflows; here
each form is written out by hand, never generated from the reader's own lists.
"""

import re
from typing import Any

import pytest
from check_names import UnreadableNameError, clashes, names, off_pull_request, triggers

SWITCH = (
    "${{ github.event_name == 'pull_request' && 'mutations' || 'mutations (no pull request)' }}"
)
GATE: dict[Any, Any] = {
    True: {"pull_request": {"branches": ["develop", "main"]}},
    "jobs": {"lint": {"name": "lint"}, "mutations": {"name": SWITCH}},
}


def by_hand(**job: Any) -> dict[Any, Any]:  # noqa: ANN401 - parsed YAML is untyped
    return {True: {"workflow_dispatch": None}, "jobs": {"shape": job}}


@pytest.mark.parametrize(
    ("job", "reported"),
    [
        pytest.param({"name": "lint"}, "'lint'", id="the-same-literal"),
        pytest.param({}, "'lint'", id="no-name-and-the-key-of-a-pull-request-job"),
        pytest.param({"name": "  LINT "}, "'  LINT '", id="another-case-and-spacing"),
        pytest.param(
            {"name": "${{ github.event_name == 'pull_request' && 'shape' || 'lint' }}"},
            "'lint'",
            id="a-switch-whose-other-name-is-one",
        ),
    ],
)
def test_a_hand_started_job_reporting_a_pull_request_name_is_found(
    job: dict[str, Any], reported: str
) -> None:
    by_hand_only = {True: {"workflow_dispatch": None}, "jobs": {"lint": job}}
    assert clashes({"ci.yml": GATE, "by-hand.yml": by_hand_only}) == [
        (
            f"by-hand.yml:lint reports {reported} on workflow_dispatch,"
            " the name pull-request job ci.yml:lint reports"
        )
    ]


def test_a_job_reporting_its_own_pull_request_name_on_a_dispatch_is_found() -> None:
    both = {True: {"pull_request": None, "workflow_dispatch": None}, "jobs": {"m": {"name": "m"}}}
    assert clashes({"m.yml": both}) == [
        "m.yml:m reports 'm' on workflow_dispatch, the name pull-request job m.yml:m reports"
    ]


def test_every_pull_request_job_of_that_name_is_named() -> None:
    other = {True: ["pull_request"], "jobs": {"lint": {}}}
    found = clashes({"ci.yml": GATE, "other.yml": other, "x.yml": by_hand(name="lint")})
    assert found == [
        (
            "x.yml:shape reports 'lint' on workflow_dispatch,"
            " the name pull-request job ci.yml:lint and other.yml:lint reports"
        )
    ]


def test_the_switch_reports_its_other_name_off_a_pull_request() -> None:
    jobs = {"mutations": {"name": SWITCH}}
    mutations = {True: {"pull_request": None, "workflow_dispatch": None}, "jobs": jobs}
    assert clashes({"ci.yml": GATE, "mutations.yml": mutations}) == []


def test_a_hand_started_job_with_a_name_of_its_own_is_not_found() -> None:
    assert clashes({"ci.yml": GATE, "x.yml": by_hand(name="shape")}) == []


def test_a_pull_request_name_on_a_workflow_with_no_pull_request_is_not_judged_as_one() -> None:
    assert clashes({"a.yml": by_hand(name="lint"), "b.yml": by_hand(name="lint")}) == []


@pytest.mark.parametrize(
    ("events", "judged"),
    [
        pytest.param({"push": {"branches": ["develop", "main"]}}, [], id="a-trunk-push"),
        pytest.param({"push": {"branches": ["main"]}}, [], id="a-push-to-main-alone"),
        pytest.param({"push": None}, ["push"], id="a-push-to-every-branch"),
        pytest.param({"push": {"branches": ["coverage/**"]}}, ["push"], id="a-scratch-push"),
        pytest.param({"push": {"branches": ["develop", "x"]}}, ["push"], id="trunk-and-another"),
        pytest.param({"push": {"branches": ["develop*"]}}, ["push"], id="a-trunk-pattern"),
        pytest.param({"push": {"branches": []}}, ["push"], id="no-branches"),
        pytest.param({"push": {"branches": "develop"}}, ["push"], id="branches-as-text"),
        pytest.param({"push": {"branches": [["main"]]}}, ["push"], id="a-branch-not-text"),
        pytest.param({"push": {"branches-ignore": ["x"]}}, ["push"], id="branches-ignored"),
        pytest.param({"push": {"tags": ["v*"]}}, ["push"], id="tags"),
        pytest.param(
            {"push": {"branches": ["main"], "paths": ["src/**"]}}, ["push"], id="trunk-and-paths"
        ),
        pytest.param({"pull_request": None}, [], id="a-pull-request"),
        pytest.param({"pull_request_target": None}, ["pull_request_target"], id="its-target"),
        pytest.param({"merge_group": None}, ["merge_group"], id="a-merge-queue"),
        pytest.param({"schedule": [{"cron": "0 0 * * *"}]}, ["schedule"], id="a-schedule"),
        pytest.param({"workflow_run": {}}, ["workflow_run"], id="another-run"),
    ],
)
def test_the_events_judged_are_every_one_but_a_pull_request_and_a_trunk_push(
    events: dict[str, Any], judged: list[str]
) -> None:
    assert off_pull_request(events) == judged


@pytest.mark.parametrize(
    ("on", "events"),
    [
        pytest.param("push", {"push": None}, id="one-event-as-text"),
        pytest.param(["push", "pull_request"], {"push": None, "pull_request": None}, id="a-list"),
        pytest.param({"workflow_dispatch": None}, {"workflow_dispatch": None}, id="a-mapping"),
    ],
)
def test_events_are_read_in_every_form_a_workflow_writes_them(
    on: object, events: dict[str, Any]
) -> None:
    assert triggers({True: on}, "x.yml") == events


def test_events_under_a_text_on_key_are_read() -> None:
    assert triggers({"on": "push"}, "x.yml") == {"push": None}


@pytest.mark.parametrize(
    "on",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="an-empty-list"),
        pytest.param({}, id="an-empty-mapping"),
        pytest.param([1], id="a-list-of-other-than-text"),
        pytest.param({1: None}, id="a-mapping-of-other-than-text"),
        pytest.param(7, id="a-number"),
    ],
)
def test_events_that_cannot_be_read_are_refused_by_name(on: object) -> None:
    with pytest.raises(UnreadableNameError, match=r"^x\.yml: cannot read its events: "):
        triggers({True: on}, "x.yml")


@pytest.mark.parametrize(
    ("job", "refusal"),
    [
        pytest.param("lint", "is not a mapping", id="not-a-mapping"),
        pytest.param({"uses": "./.github/workflows/b.yml"}, "calls a reusable", id="reusable"),
        pytest.param({"strategy": {"matrix": {"py": ["3.13"]}}}, "has a matrix", id="matrix"),
        pytest.param({"name": 3}, "name is not text", id="a-number"),
        pytest.param({"name": "  "}, "name is not text", id="blank"),
        pytest.param({"name": "test (${{ matrix.py }})"}, "cannot read", id="a-matrix-value"),
        pytest.param({"name": "${{ inputs.name }}"}, "cannot read", id="an-input"),
        pytest.param(
            {"name": "${{ github.event_name == 'pull_request' && '' || 'b' }}"},
            "cannot read",
            id="a-switch-with-no-pull-request-name",
        ),
        pytest.param(
            {"name": "${{ github.event_name != 'pull_request' && 'a' || 'b' }}"},
            "cannot read",
            id="a-switch-the-other-way-round",
        ),
        pytest.param(
            {"name": "${{ github.event_name == 'pull_request' && 'a' || 'b' }} x"},
            "cannot read",
            id="a-switch-with-text-after",
        ),
        pytest.param(
            {"name": "${{ github.event_name == 'pull_request' && 'a' || '${{ x }}' }}"},
            "cannot read",
            id="a-switch-holding-an-expression",
        ),
    ],
)
def test_a_name_that_cannot_be_read_exactly_is_refused_by_name(job: object, refusal: str) -> None:
    with pytest.raises(UnreadableNameError, match=rf"^x\.yml: job k.*{re.escape(refusal)}"):
        names("k", job, "x.yml")


@pytest.mark.parametrize(
    ("job", "reported"),
    [
        pytest.param({}, ("k", "k"), id="no-name-is-its-key"),
        pytest.param({"name": "lint"}, ("lint", "lint"), id="a-literal"),
        pytest.param({"name": SWITCH}, ("mutations", "mutations (no pull request)"), id="switch"),
        pytest.param({"strategy": {"fail-fast": False}}, ("k", "k"), id="a-strategy-no-matrix"),
        pytest.param({"strategy": None}, ("k", "k"), id="an-empty-strategy"),
    ],
)
def test_the_names_a_job_reports_are_read(job: dict[str, Any], reported: tuple[str, str]) -> None:
    assert names("k", job, "x.yml") == reported


@pytest.mark.parametrize(
    "jobs",
    [pytest.param(None, id="none"), pytest.param({}, id="empty"), pytest.param([], id="a-list")],
)
def test_a_workflow_whose_jobs_cannot_be_read_is_refused_by_name(jobs: object) -> None:
    with pytest.raises(UnreadableNameError, match=r"^x\.yml: cannot read its jobs: "):
        clashes({"x.yml": {True: "push", "jobs": jobs}})
