"""The integration suites run in their own CI jobs, each with one limit at its step (#286): the
Python suite on every Python the unit suite runs on, the extension's in its workspace."""

import re
from typing import Any

from ci_workflow import ci

INTEGRATION_RUN = "uv run --locked pytest -W error --suite integration -p no:cacheprovider"
# The suite again under coverage, unlimited, so the limit never times the tracer (#374); its data
# goes to the coverage job (#446).
INTEGRATION_MEASURED = (
    'mkdir -p "${RUNNER_TEMP}/coverage-report"\n'
    'COVERAGE_FILE="${RUNNER_TEMP}/coverage-report/.coverage.${GITHUB_JOB}"'
    f" {INTEGRATION_RUN} --cov --cov-report=term\n"
)
# What runs a suite: pytest's suite option, vitest's project option, or an npm script for either.
SUITE_RUN = re.compile(r"--suite integration|--project integration|test:integration")


def job(name: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = ci()["jobs"]
    assert name in jobs, sorted(jobs)
    return jobs[name]


def test_the_integration_suite_runs_on_the_python_the_unit_suite_runs_on() -> None:
    """One Python since #382, the one .python-version pins: neither job has a matrix, and both
    names carry its minor (tests/guards/test_versions.py checks it against the pin)."""
    assert "strategy" not in job("integration")
    assert "strategy" not in job("test")
    assert job("test")["name"] == "test (py3.13)"
    assert job("integration")["name"] == "integration (py3.13)"


def test_the_integration_job_runs_the_integration_suite_alone_with_one_limit() -> None:
    steps = job("integration")["steps"]
    assert [step["run"] for step in steps if "pytest" in str(step.get("run", ""))] == [
        INTEGRATION_RUN,
        INTEGRATION_MEASURED,
    ]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert [step["run"] for step in limited] == [INTEGRATION_RUN]
    # #292 moved the long real runs here (the golden window's CLI, paper and backtest runs). The
    # step took 31 s on CI on both Pythons (PR #316, run 38331680081), against #286's 6 s; a step
    # limit is whole minutes, and 3 is about six times the measured run.
    assert limited[0]["timeout-minutes"] == 3


BROWSERS = ("chromium", "chrome", "msedge")
# Each browser's run writes its JSON report, which the shared one-suite checks read (#579).
BROWSER_RUN = "npm run test:browser -- --project={browser} --reporter=list,json"
FIRST_BROWSER_RUN = BROWSER_RUN.format(browser=BROWSERS[0])
ONE_SUITE_STEP = "The same tests on every browser"
ONE_SUITE_RUN = (
    "npx playwright test --list --reporter=json > reports/list.json\n"
    "npx one-suite --group desktop=chromium,chrome,msedge --list reports/list.json \\\n"
    "  --report reports/chromium.json --report reports/chrome.json --report reports/msedge.json\n"
)


def test_the_extension_integration_job_runs_its_suites_each_with_one_limit() -> None:
    steps = job("extension-integration")["steps"]
    npm = [step for step in steps if "npm " in str(step.get("run", ""))]
    assert [step["run"] for step in npm] == [
        "npm ci --ignore-scripts",
        "npm run test:integration",
        *(BROWSER_RUN.format(browser=browser) for browser in BROWSERS),
    ]
    assert [step.get("working-directory") for step in npm] == ["extension"] * 5
    one_suite = steps[[step.get("name") for step in steps].index(ONE_SUITE_STEP)]
    limited = [step for step in steps if "timeout-minutes" in step]
    assert limited == [*npm[1:], one_suite]
    # The integration suite measured on the laptop on 2026-10-13: 3 s. The browser suite runs
    # only in CI (#231): its limit is set from its first CI run, the same on each browser (#501).
    # The one-suite checks only list the tests and read three reports (#579).
    assert [step["timeout-minutes"] for step in limited] == [1, 2, 2, 2, 1]


def test_each_browser_run_writes_its_own_json_report() -> None:
    steps = job("extension-integration")["steps"]
    runs = [step.get("run") for step in steps]
    for browser in BROWSERS:
        step = steps[runs.index(BROWSER_RUN.format(browser=browser))]
        assert step["env"] == {"PLAYWRIGHT_JSON_OUTPUT_FILE": f"reports/{browser}.json"}


def test_the_shared_one_suite_checks_read_every_browser_s_report_after_the_last_run() -> None:
    # One suite, unchanged on every browser (#579, shyden-labs/playwright-devices#16): the list of
    # what each browser should run, checked against what each ran, in one group.
    steps = job("extension-integration")["steps"]
    names = [step.get("name") for step in steps]
    runs = [step.get("run") for step in steps]
    at = names.index(ONE_SUITE_STEP)
    assert steps[at]["run"] == ONE_SUITE_RUN
    assert steps[at]["working-directory"] == "extension"
    assert steps[at]["if"] == "steps.scope.outputs.docs_only != 'true'"
    assert at > runs.index(BROWSER_RUN.format(browser=BROWSERS[-1]))


def test_every_browser_is_installed_by_the_locked_playwright_before_the_browser_suite() -> None:
    # One suite, run unchanged on every browser the extension supports (#501): Chromium, Google
    # Chrome and Microsoft Edge, each run on its own so each prints its own total.
    steps = job("extension-integration")["steps"]
    runs = [step.get("run") for step in steps]
    install = runs.index("npx playwright install --with-deps " + " ".join(BROWSERS))
    assert install < runs.index(FIRST_BROWSER_RUN)
    assert steps[install].get("working-directory") == "extension"


def test_no_other_job_runs_an_integration_suite() -> None:
    # A set: the integration job runs the suite twice, limited and measured (#374).
    runners = sorted(
        {
            name
            for name, found in ci()["jobs"].items()
            for step in found["steps"]
            if SUITE_RUN.search(str(step.get("run", "")))
        }
    )
    assert runners == ["extension-integration", "integration"]


def test_the_dev_deploy_waits_for_both_integration_jobs() -> None:
    needs = job("deploy-dev")["needs"]
    assert {"integration", "extension-integration"} <= set(needs)


SCREEN_STEP = "A screen with a window manager for the side panel"


def test_the_browser_suite_runs_on_a_screen_with_a_window_manager() -> None:
    # The side panel is browser UI, opened by a real click on the extension's button (#503): each
    # browser runs in a window on an X display with a window manager, xdotool clicks and ImageMagick
    # takes the screenshots the button is found in. The display carries over to later steps.
    steps = job("extension-integration")["steps"]
    names = [step.get("name") for step in steps]
    screen = steps[names.index(SCREEN_STEP)]
    run = screen["run"]
    assert "apt-get install -y xvfb openbox xdotool imagemagick" in run
    assert "Xvfb :99 -screen 0 1280x800x24 &" in run
    assert "DISPLAY=:99 openbox &" in run
    assert 'echo "DISPLAY=:99" >> "$GITHUB_ENV"' in run
    runs = [step.get("run") for step in steps]
    assert names.index(SCREEN_STEP) < runs.index(FIRST_BROWSER_RUN)


FAILED_SCREENS_STEP = "Keep what the screen showed when the browser suite failed"


def test_a_failed_browser_suite_keeps_what_the_screen_showed() -> None:
    # A failed click on the extension's button is judged by the screen it was looking at (#503):
    # the suite saves that screen in its output folder, and the job keeps the folder on failure.
    steps = job("extension-integration")["steps"]
    names = [step.get("name") for step in steps]
    keep = steps[names.index(FAILED_SCREENS_STEP)]
    assert keep["if"] == "failure() && steps.scope.outputs.docs_only != 'true'"
    assert keep["uses"].startswith("actions/upload-artifact@")
    assert keep["with"]["path"] == "extension/test-results/"
    assert names.index(FAILED_SCREENS_STEP) == len(names) - 1
