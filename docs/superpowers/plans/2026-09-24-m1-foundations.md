# M1 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the steadyhand monorepo so that every later milestone lands on green, enforced quality gates: a uv workspace with both packages, CI, supply-chain and codebase meta-guards, and the engine's first value types (`Money`, the trading types, `Portfolio`) plus the `MarketRules`, `DataSource` and `Broker` protocols.

**Architecture:** One public uv workspace with two hatchling packages under `packages/`. The engine (`steadyhand`) uses only the standard library at runtime. Its value types are frozen dataclasses that validate themselves when constructed, so bad data fails where it enters. `Portfolio` is an immutable snapshot: each operation returns a new one. Cash is a ledger of signed movements, each carrying the date it settles, so T+2 falls out of a date comparison. Meta-guards are ordinary pytest tests that read the AST or parsed YAML, never raw text, so a comment can never satisfy them.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18 workspace, hatchling, pytest + pytest-cov + hypothesis, mypy `--strict`, ruff, pip-audit, PyYAML (tests only), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (M1 is §13 item 1; the sections it implements are §4.1–4.4, §10.1, §10.2 in part, §10.4 security in part, §10.5, §11).

## Global Constraints

- Engine runtime dependencies: **standard library only** (§4.2). `packages/steadyhand/pyproject.toml` has `dependencies = []`.
- `float` never appears in `money.py`, `portfolio.py`, `sizing.py`, `risk.py`, `income.py`, `metrics.py` or `broker/` (§4.4, §10.1).
- Money is an **integer amount in minor units** plus a `Currency`; for IDR one unit is one rupiah. Rates and weights are `Decimal` (§4.4).
- Rounding is explicit and against the trader: what you pay rounds up, what you receive rounds down (§4.4).
- TDD: a test is written and shown failing before production code. New tests run first against stubs that raise `NotImplementedError("<name>")`. Any test that passes against a stub is a finding: it is either listed in the step's expected output with its reason, or it is fixed. A bare `raises(Exception)` is not accepted: every `pytest.raises` has a `match=` on the message (§10).
- Every third-party `uses:` is a full 40-hex commit SHA followed by `# vX.Y.Z` (§10.1).
- Dependabot covers `uv` and `github-actions`, weekly, `target-branch: develop`, with a same-repo sub-path group above the patch group (§10.1, §11).
- Quality gates (§10.5): `ruff check`, `ruff format --check`, `mypy --strict`, `pytest -W error` with **100% branch coverage** for both packages, the meta-guards, pip-audit, and a build of both wheels.
- Branches: each story gets its own branch, merged into `develop` by PR. Nothing merges straight into `main` (§11).
- English only. The phrase "robot trading" never appears (§1.3).
- The disclaimer, verbatim: `steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.`
- Test file basenames are unique across `tests/`, because mypy maps each test file to a top-level module name (there are no `__init__.py` files in `tests/`).

## Review Focus

1. **A large amount times a rate** (`Money(10**40 + 1, IDR).times(Decimal("0.0015"), Rounding.UP)`): Decimal's default 28-digit context would round the product *before* our explicit rounding. The expected result is exact (`15 * 10**36 + 1`). Pinned in Task 3 (`test_huge_amounts_are_exact`).
2. **A `bool` or `float` where an `int` is expected** (`Money(True, IDR)`, `Money(1.5, IDR)`, `Order(..., quantity=True, ...)`, `Money * 1.5`): `bool` is a subclass of `int`, so a lazy `isinstance` check accepts it. Each is refused with a message naming the type. Pinned in Tasks 3 and 4.
3. **A `datetime` where a `date` is expected**: `datetime` is a subclass of `date`, and comparing the two raises later, far from the cause. It is refused where it enters (bars, orders, fills, portfolio operations). Pinned in Tasks 4 and 5.
4. **A back-dated portfolio operation** (a fill dated before the last recorded movement): refused with `ChronologyError`, and the original portfolio is unchanged. Pinned in Task 5.
5. **Recycling sale proceeds on the same day** (sell today, then buy today with that money): refused with `InsufficientCashError`, because the proceeds settle at T+2. Pinned in Task 5 (`test_sale_proceeds_cannot_fund_a_same_day_buy`).

## Scope decisions (read before starting)

- **Deferred to M3:** entitlements and splits on `Portfolio`, because they need corporate-action timing (§5 step 2). M1 defines the corporate-action *types* only.
- **Deferred to M3 (`MarketView`, `Strategy`):** the `Strategy` protocol needs `MarketView`, which enforces no look-ahead (§4.3), and that belongs with the engine loop.
- **`ManualBroker` stub:** not built. A stub raising `NotImplementedError` in shipped code is dead code. It arrives with B+C's Confirm Fill flow.
- **Moved into M1 from M10: TestPyPI dev publishing (Task 8).** The spec's §11 says a merge into `develop` publishes to TestPyPI, and the operator's standing rule is to deploy after every `develop` merge. Task 8 is blocked on OP-1 (the operator sets up trusted publishers). PyPI releases stay in M10.
- **Signature changes from §4.3 (illustrative there):** `dividend_tax` takes `reinvested_by_deadline` as keyword-only, because a positional `bool` reads as `dividend_tax(gross, True, day)` at the call site and ruff's FBT rule rejects it. `round_to_tick` keeps `side: Side`, where BUY rounds up and SELL rounds down.

## File map

| File | Task | Responsibility |
|---|---|---|
| `pyproject.toml` | 1 | Workspace root (not published): members, dev tools, ruff/mypy/pytest/coverage config |
| `.python-version`, `.gitignore` | 1 | Default interpreter; ignored caches and local state |
| `packages/steadyhand/pyproject.toml`, `README.md`, `LICENSE` | 1 | Engine distribution metadata |
| `packages/steadyhand/src/steadyhand/__init__.py`, `py.typed` | 1, 7 | Public API (version in Task 1, every export in Task 7) |
| `packages/steadyhand-idx/pyproject.toml`, `README.md`, `LICENSE` | 1 | IDX distribution metadata |
| `packages/steadyhand-idx/src/steadyhand_idx/__init__.py`, `py.typed` | 1 | IDX package version |
| `.github/workflows/ci.yml` | 1, 8 | The quality gates; dev publishing in Task 8 |
| `.github/dependabot.yml` | 2 | Weekly updates for uv and actions, targeting develop |
| `packages/steadyhand/src/steadyhand/money.py` | 3 | `Currency`, `IDR`, `Rounding`, `Money`, `CurrencyMismatchError` |
| `packages/steadyhand/src/steadyhand/_validate.py` | 4 | Shared `require_date` / `require_int` checks |
| `packages/steadyhand/src/steadyhand/types.py` | 4 | `Side`, `Instrument`, `Bar`, corporate actions, `Order`, `OrderAck`, `Costs`, `Fill`, `Position` |
| `packages/steadyhand/src/steadyhand/portfolio.py` | 5 | `Portfolio`, `CashMovement`, `MovementKind`, the portfolio errors |
| `packages/steadyhand/src/steadyhand/market.py` | 6 | `MarketRules` protocol |
| `packages/steadyhand/src/steadyhand/data.py` | 6 | `DataSource` protocol, `DataUnavailableError` |
| `packages/steadyhand/src/steadyhand/broker/__init__.py`, `protocol.py` | 6 | `Broker` protocol |
| `packages/steadyhand/src/steadyhand/disclaimer.py` | 7 | `DISCLAIMER` constant |
| `scripts/set_dev_version.py` | 8 | Rewrites both versions to `X.Y.Z.devN` before a TestPyPI upload |
| `tests/conftest.py` | 1 | Hypothesis profiles |
| `tests/engine/*.py`, `tests/idx/*.py`, `tests/meta/*.py`, `tests/scripts/*.py` | 1–8 | Per-package tests, meta-guards, script tests |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts. The "Acceptance criteria" block in each task is the text of the story. Task 0 is operator-assisted setup, not a code story.

| Task | Story | Branch |
|---|---|---|
| 0 | Repository settings and board (chore) | none |
| 1 | S1 Workspace, quality gates and CI | `m1/s1-workspace-ci` |
| 2 | S2 Supply-chain guard and Dependabot | `m1/s2-supply-chain` |
| 3 | S3 Money | `m1/s3-money` |
| 4 | S4 Trading value types | `m1/s4-types` |
| 5 | S5 Portfolio | `m1/s5-portfolio` |
| 6 | S6 Plug-in protocols | `m1/s6-protocols` |
| 7 | S7 Codebase meta-guards and public API | `m1/s7-meta-guards` |
| 8 | S8 TestPyPI dev publishing (blocked on OP-1) | `m1/s8-dev-publish` |

**Merging a story (every task):** push the branch, and open a PR into `develop` whose body says `Refs #<story>` (never `close`/`fix`/`resolve` next to a number). Write the PR head SHA to a file, so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name: each must be `success`. `gh pr view --json statusCheckRollup` is not enough on its own, because it carries no commit SHA per check. Only then merge with `gh pr merge <pr> --squash --delete-branch`, and close the story with a comment linking the PR.

**Pushing:** agent sessions cannot push to `ShydenMcM/steadyhand` (see `HANDOVER.md`). Until that changes, each "push" step means asking Shyden to run the printed `git push` command in a normal terminal.

---

### Task 0: Repository settings and board

Steps 1 to 4 need the operator's first push to have landed. Steps 5 and 6 (the board and the stories) do not, so they can run first. There are no code changes, so there is no TDD cycle: each step is verified by reading the setting back.

- [ ] **Step 1: Confirm both branches are on GitHub**

Run: `git ls-remote --heads origin`
Expected: two lines, `refs/heads/develop` and `refs/heads/main`. If either is missing, stop and ask Shyden.

- [ ] **Step 2: Make `develop` the default branch and set merge options**

```bash
gh repo edit ShydenMcM/steadyhand --default-branch develop \
  --enable-squash-merge --enable-merge-commit --enable-rebase-merge=false \
  --delete-branch-on-merge
gh repo view ShydenMcM/steadyhand --json defaultBranchRef,squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed,deleteBranchOnMerge
```
Expected: `"name":"develop"`, `squashMergeAllowed:true`, `mergeCommitAllowed:true` (release PRs from `develop` into `main` use merge commits), `rebaseMergeAllowed:false`, `deleteBranchOnMerge:true`.

- [ ] **Step 3: Turn on secret scanning and push protection, then read them back**

```bash
gh api -X PATCH repos/ShydenMcM/steadyhand --input - <<'EOF'
{"security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}
EOF
gh api repos/ShydenMcM/steadyhand --jq '.security_and_analysis | {secret_scanning: .secret_scanning.status, push_protection: .secret_scanning_push_protection.status}'
gh api repos/ShydenMcM/steadyhand/automated-security-fixes
```
Expected: `{"secret_scanning":"enabled","push_protection":"enabled"}` and `{"enabled":true,"paused":false}`.

- [ ] **Step 4: Protect `main` and `develop` (no required checks yet)**

A CI job can only be required once it exists on `develop`, so required checks are added in Task 1, step 13.

```bash
for branch in main develop; do
gh api -X PUT "repos/ShydenMcM/steadyhand/branches/${branch}/protection" --input - <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0, "dismiss_stale_reviews": true},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
done
for branch in main develop; do
  gh api "repos/ShydenMcM/steadyhand/branches/${branch}/protection" \
    --jq "{branch: \"${branch}\", admins: .enforce_admins.enabled, force: .allow_force_pushes.enabled, delete: .allow_deletions.enabled, reviews: .required_pull_request_reviews.required_approving_review_count}"
done
```
Expected, for both branches: `admins:true, force:false, delete:false, reviews:0`.

- [ ] **Step 5: Create the board, assert its title, and link it to the repo**

```bash
gh project create --owner ShydenMcM --title steadyhand --format json > "${TMPDIR}/board.json"
python3 -c 'import json,os; b=json.load(open(os.environ["TMPDIR"]+"/board.json")); print(b["number"], b["id"], b["title"])'
```
Expected: `<number> <node id> steadyhand`. Record the number and the node id in `HANDOVER.md`. Before any write to the board, resolve it from the node id and check the title:

```bash
gh api graphql -f query='query($id:ID!){node(id:$id){... on ProjectV2{number title owner{... on User{login}}}}}' -f id="<node id>"
gh project link <number> --owner ShydenMcM --repo ShydenMcM/steadyhand
```
Expected: `title` is `steadyhand` and `login` is `ShydenMcM`. The link command prints no error.

- [ ] **Step 6: File the eight stories and write their numbers into this plan**

For each of Tasks 1 to 8, create an issue whose title is the story name from the **Stories** table and whose body is that task's **Acceptance criteria** block, then add it to the board:

```bash
gh issue create --repo ShydenMcM/steadyhand --title "S1 Workspace, quality gates and CI" --body-file "${TMPDIR}/s1.md"
gh project item-add <number> --owner ShydenMcM --url <issue url>
```

Read each item back with `gh project item-list <number> --owner ShydenMcM --format json` and check that all eight are there. Then replace each `<Sn issue>` in this plan with the real number (`Refs #12`, for example), and commit the plan. Every "Refs" line in the tasks below uses those numbers.

---

### Task 1: S1 Workspace, quality gates and CI

**Acceptance criteria (story text):**
1. `uv sync --locked` on a fresh clone installs both packages (editable) and every dev tool, with uv pinned to 0.12.18 through `required-version`.
2. Both packages build as wheels and sdists (`uv build --all-packages`). The engine wheel installs into a fresh virtualenv with no other package and imports.
3. `steadyhand.__version__` and `steadyhand_idx.__version__` equal the version in each package's `pyproject.toml`.
4. Each package directory ships a `LICENSE` identical to the root licence, and a `README.md` carrying the disclaimer verbatim.
5. CI on every PR into `develop` or `main` and every push to them runs `lint`, `test (py3.12)`, `test (py3.13)`, `audit` and `build`. `test` runs pytest with warnings as errors and fails under 100% branch coverage. `audit` fails on any known vulnerability.
6. Every `uses:` in the workflow is a 40-hex SHA with a `# vX.Y.Z` comment (enforced mechanically from Task 2).
7. After merge, those five contexts are required on `develop` and `main` with `strict: true`, as confirmed by reading the protection back.

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `uv.lock` (generated)
- Create: `packages/steadyhand/{pyproject.toml,README.md,LICENSE}`, `packages/steadyhand/src/steadyhand/{__init__.py,py.typed}`
- Create: `packages/steadyhand-idx/{pyproject.toml,README.md,LICENSE}`, `packages/steadyhand-idx/src/steadyhand_idx/{__init__.py,py.typed}`
- Create: `.github/workflows/ci.yml`
- Test: `tests/conftest.py`, `tests/engine/test_engine_package.py`, `tests/idx/test_idx_package.py`, `tests/meta/test_packaging.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `steadyhand.__version__: str`, `steadyhand.__all__: list[str]`, `steadyhand_idx.__version__: str`, `steadyhand_idx.__all__: list[str]`. CI job names `lint`, `test (py3.12)`, `test (py3.13)`, `audit` and `build` are the required contexts. Every later task relies on the `pytest`, `ruff`, `mypy` commands configured here.

- [ ] **Step 1: Pin uv and branch**

```bash
uv self update 0.12.18
uv --version
git switch develop && git switch -c m1/s1-workspace-ci
```
Expected: `uv 0.12.18 (...)`.

- [ ] **Step 2: Write the workspace root**

File: `pyproject.toml`

```toml
[project]
name = "steadyhand-workspace"
version = "0.0.0"
description = "Development workspace for steadyhand and steadyhand-idx. Not published."
requires-python = ">=3.12"
dependencies = ["steadyhand", "steadyhand-idx"]

[tool.uv]
package = false
required-version = "==0.12.18"

[tool.uv.workspace]
members = ["packages/steadyhand", "packages/steadyhand-idx"]

[tool.uv.sources]
steadyhand = { workspace = true }
steadyhand-idx = { workspace = true }

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF", "S", "PT", "PL", "ANN",
    "ERA", "T20", "DTZ", "PIE", "RET", "TRY", "FBT", "PTH", "ISC", "Q", "TID", "ARG",
    "BLE", "EM",
]
ignore = [
    "TRY003",  # messages are the contract (spec §10): every error names what went wrong
]

[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version"]

[tool.ruff.lint.per-file-ignores]
# Tests assert, use literal values, pass bools on purpose, and implement interfaces minimally.
"tests/**" = ["S101", "PLR2004", "FBT003", "ARG002", "PLR0913", "PLR0917"]
"scripts/**" = ["T201"]

[tool.mypy]
strict = true
python_version = "3.12"
files = ["packages", "tests"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra"]
filterwarnings = ["error"]
xfail_strict = true

[tool.coverage.run]
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx"]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = true
# A Protocol method body is a bare `...` that never runs; it is not untested code.
exclude_also = ['^\s*\.\.\.$']
```

File: `.python-version`

```
3.12
```

File: `.gitignore`

```
# Python
__pycache__/
*.py[cod]
.venv/
build/
dist/
*.egg-info/

# Tool caches
.coverage
.coverage.*
.hypothesis/
.mypy_cache/
.pytest_cache/
.ruff_cache/
coverage.xml
htmlcov/

# Local state. The app keeps its SQLite files in the user's data directory; these catch strays.
*.db
*.sqlite
*.sqlite3

# Session tooling
.remember/
```

- [ ] **Step 3: Write the two packages (metadata, readme, licence, docstring-only `__init__`)**

File: `packages/steadyhand/pyproject.toml`

```toml
[build-system]
requires = ["hatchling>=1.32,<2"]
build-backend = "hatchling.build"

[project]
name = "steadyhand"
version = "0.1.0"
description = "A market-neutral engine for self-hosted, dividend-first portfolio bots: backtests, paper trading and risk controls."
readme = "README.md"
requires-python = ">=3.12"
license = "Apache-2.0"
license-files = ["LICENSE"]
authors = [{ name = "Shyden" }]
classifiers = [
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business :: Financial :: Investment",
    "Typing :: Typed",
]
# The engine depends on the standard library only (spec §4.2). A meta-guard enforces this.
dependencies = []

[project.urls]
Homepage = "https://github.com/ShydenMcM/steadyhand"
Issues = "https://github.com/ShydenMcM/steadyhand/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/steadyhand"]
```

File: `packages/steadyhand-idx/pyproject.toml`

```toml
[build-system]
requires = ["hatchling>=1.32,<2"]
build-backend = "hatchling.build"

[project]
name = "steadyhand-idx"
version = "0.1.0"
description = "The Indonesia Stock Exchange distribution of steadyhand: IDX rules, Yahoo .JK data, paper trading and a CLI."
readme = "README.md"
requires-python = ">=3.12"
license = "Apache-2.0"
license-files = ["LICENSE"]
authors = [{ name = "Shyden" }]
classifiers = [
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: End Users/Desktop",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business :: Financial :: Investment",
    "Typing :: Typed",
]
dependencies = [
    "steadyhand",
]

[project.urls]
Homepage = "https://github.com/ShydenMcM/steadyhand"
Issues = "https://github.com/ShydenMcM/steadyhand/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/steadyhand_idx"]
```

File: `packages/steadyhand/README.md`

```markdown
# steadyhand

A market-neutral Python engine for self-hosted, dividend-first portfolio bots: strategies, a simulated broker, risk controls, a backtester and income tracking.

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```

File: `packages/steadyhand-idx/README.md`

```markdown
# steadyhand-idx

The Indonesia Stock Exchange (IDX) distribution of steadyhand: IDX trading rules, Yahoo Finance `.JK` data, paper trading and a CLI.

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```

Copy the licence into both packages. Hatchling reads `license-files` relative to each package, and `uv sync` builds package metadata, so the copies must exist before step 4:

```bash
cp LICENSE packages/steadyhand/LICENSE
cp LICENSE packages/steadyhand-idx/LICENSE
touch packages/steadyhand/src/steadyhand/py.typed packages/steadyhand-idx/src/steadyhand_idx/py.typed
```

File: `packages/steadyhand/src/steadyhand/__init__.py` (stub)

```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""
```

File: `packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (stub)

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""
```

- [ ] **Step 4: Add the dev tools and create the lock**

```bash
uv add --dev pytest pytest-cov hypothesis mypy ruff pip-audit pyyaml types-pyyaml
uv sync --locked
```
Expected: `uv.lock` is created, and `uv add` appends a `[dependency-groups]` table listing the eight tools to `pyproject.toml`. Keep both. `uv sync --locked` then reports nothing to change.

- [ ] **Step 5: Write the failing tests**

File: `tests/conftest.py`

```python
"""Settings shared by every test suite in the workspace."""

import os

from hypothesis import settings

settings.register_profile("dev", max_examples=100)
settings.register_profile("ci", max_examples=500, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
```

File: `tests/engine/test_engine_package.py`

```python
"""The engine package is installed from this workspace and reports its own version."""

import tomllib
from pathlib import Path

import steadyhand

ROOT = Path(__file__).resolve().parents[2]


def test_version_matches_the_package_pyproject() -> None:
    pyproject = tomllib.loads(
        (ROOT / "packages/steadyhand/pyproject.toml").read_text(encoding="utf-8")
    )
    assert steadyhand.__version__ == pyproject["project"]["version"]


def test_every_exported_name_resolves() -> None:
    assert "__version__" in steadyhand.__all__
    missing = [name for name in steadyhand.__all__ if not hasattr(steadyhand, name)]
    assert missing == []
```

File: `tests/idx/test_idx_package.py`

```python
"""The IDX package is installed from this workspace and reports its own version."""

import tomllib
from pathlib import Path

import steadyhand_idx

ROOT = Path(__file__).resolve().parents[2]


def test_version_matches_the_package_pyproject() -> None:
    pyproject = tomllib.loads(
        (ROOT / "packages/steadyhand-idx/pyproject.toml").read_text(encoding="utf-8")
    )
    assert steadyhand_idx.__version__ == pyproject["project"]["version"]


def test_every_exported_name_resolves() -> None:
    assert "__version__" in steadyhand_idx.__all__
    missing = [name for name in steadyhand_idx.__all__ if not hasattr(steadyhand_idx, name)]
    assert missing == []
```

File: `tests/meta/test_packaging.py`

```python
"""Each published package carries the project's licence."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_each_package_ships_the_root_licence() -> None:
    root_licence = (ROOT / "LICENSE").read_bytes()
    packages = sorted(p for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file())
    assert [p.name for p in packages] == ["steadyhand", "steadyhand-idx"]
    for package in packages:
        assert (package / "LICENSE").read_bytes() == root_licence, package.name
```

- [ ] **Step 6: Run the tests and watch them fail**

Run: `uv run pytest`
Expected: 4 failed, 1 passed. Each of the four fails with `AttributeError: module 'steadyhand' has no attribute '__version__'` (or `'__all__'`, or the `steadyhand_idx` equivalents). `test_each_package_ships_the_root_licence` passes, because step 3 had to create the copies for `uv sync` to work. That is expected: the test guards against the copies drifting, not against their absence.

- [ ] **Step 7: Implement the versions**

File: `packages/steadyhand/src/steadyhand/__init__.py`

```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

__version__: str = version("steadyhand")

__all__ = ["__version__"]
```

File: `packages/steadyhand-idx/src/steadyhand_idx/__init__.py`

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

__version__: str = version("steadyhand-idx")

__all__ = ["__version__"]
```

- [ ] **Step 8: Run every gate locally**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check
uv run ruff format --check
uv run mypy
```
Expected: `5 passed`, `Required test coverage of 100% reached`, `All checks passed!`, `N files already formatted`, `Success: no issues found in N source files`. Read each output in full, not just its exit code.

- [ ] **Step 9: Prove the engine wheel stands alone**

```bash
rm -rf dist && uv build --all-packages --out-dir dist
ls dist
rm -rf "${TMPDIR}/engine-only" && uv venv "${TMPDIR}/engine-only" --python 3.12
uv pip install --python "${TMPDIR}/engine-only" dist/steadyhand-0.1.0-py3-none-any.whl
"${TMPDIR}/engine-only/bin/python" -c "import steadyhand; print(steadyhand.__version__)"
```
Expected: `dist` holds four files (`steadyhand-0.1.0.tar.gz`, `steadyhand-0.1.0-py3-none-any.whl`, `steadyhand_idx-0.1.0.tar.gz`, `steadyhand_idx-0.1.0-py3-none-any.whl`). The install lists exactly one package, and the last command prints `0.1.0`.

- [ ] **Step 10: Write the CI workflow**

The SHAs below were resolved on 2026-09-24 with `gh api repos/<owner>/<repo>/releases/latest --jq .tag_name` and `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha`. Re-resolve them the same way if this plan is executed much later, and never type a SHA from memory.

File: `.github/workflows/ci.yml`

```yaml
name: ci

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

env:
  UV_VERSION: "0.12.18"
  HYPOTHESIS_PROFILE: ci

jobs:
  lint:
    name: lint
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
      - run: uv run --locked ruff check
      - run: uv run --locked ruff format --check
      - run: uv run --locked mypy

  test:
    name: test (py${{ matrix.python }})
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ matrix.python }}
          enable-cache: true
      - run: uv sync --locked
      - run: uv run --locked pytest -W error --cov --cov-report=term-missing

  audit:
    name: audit
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
      - name: Audit every locked dependency, dev tools included
        run: |
          uv export --locked --format requirements-txt --no-emit-workspace \
            --output-file "${RUNNER_TEMP}/requirements-audit.txt"
          uv run --locked pip-audit --strict --disable-pip -r "${RUNNER_TEMP}/requirements-audit.txt"

  build:
    name: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
      - run: uv build --all-packages --out-dir dist
      - name: Both packages built a wheel and an sdist
        run: |
          ls dist
          test "$(ls dist/*.whl | wc -l)" -eq 2
          test "$(ls dist/*.tar.gz | wc -l)" -eq 2
      - name: The engine wheel installs and imports with nothing else
        run: |
          uv venv "${RUNNER_TEMP}/engine-only"
          uv pip install --python "${RUNNER_TEMP}/engine-only" dist/steadyhand-*.whl
          "${RUNNER_TEMP}/engine-only/bin/python" -c "import steadyhand; print(steadyhand.__version__)"
```

`dist/steadyhand-*.whl` matches only the engine wheel, because wheel filenames spell the IDX package `steadyhand_idx-…`.

- [ ] **Step 11: Commit**

```bash
git add .gitignore .python-version pyproject.toml uv.lock packages tests .github
git status --short
git commit -m "build: uv workspace, both packages, quality gates and CI (S1)"
```
Expected: `git status --short` shows only the files named in this task.

- [ ] **Step 12: Push, open the PR, verify, merge**

Ask Shyden to run `git push -u origin m1/s1-workspace-ci`, then check that it landed with `git ls-remote --heads origin m1/s1-workspace-ci`. Open the PR:
`gh pr create --base develop --head m1/s1-workspace-ci --title "S1: workspace, quality gates and CI" --body "Refs #<S1 issue>"`. Follow **Merging a story**. All five jobs must appear by name: `lint`, `test (py3.12)`, `test (py3.13)`, `audit` and `build`.

- [ ] **Step 13: Require the five checks on `develop` and `main`, then read them back**

```bash
for branch in develop main; do
gh api -X PUT "repos/ShydenMcM/steadyhand/branches/${branch}/protection" --input - <<'EOF'
{
  "required_status_checks": {"strict": true, "contexts": ["lint", "test (py3.12)", "test (py3.13)", "audit", "build"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0, "dismiss_stale_reviews": true},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
done
for branch in develop main; do
  gh api "repos/ShydenMcM/steadyhand/branches/${branch}/protection/required_status_checks" --jq "{branch: \"${branch}\", strict: .strict, contexts: .contexts}"
done
```
Expected, for both branches: `strict:true` and exactly the five contexts. There is nothing to deploy yet, because dev publishing arrives in Task 8.

---

### Task 2: S2 Supply-chain guard and Dependabot

**Acceptance criteria (story text):**
1. `.github/dependabot.yml` configures `uv` and `github-actions`, both weekly with `target-branch: develop`.
2. The actions config has a same-repo sub-path group (`actions/cache*`) above its patch group.
3. `tests/meta/test_supply_chain.py` fails if any `uses:` is not a 40-hex SHA, if any pin lacks a `# vX.Y.Z` comment, if an ecosystem present in the repo is not configured, if any update does not target `develop` weekly, or if the sub-path group is missing or below the patch group. It parses YAML, so comments cannot satisfy it.
4. Each rule is mutation-verified (see step 7), and the results are recorded in the PR body.

**Files:**
- Create: `.github/dependabot.yml`
- Test: `tests/meta/test_supply_chain.py`

**Interfaces:**
- Consumes: `.github/workflows/ci.yml` and `uv.lock` from Task 1.
- Produces: nothing importable. The guard covers every workflow added later, including Task 8's publish job.

- [ ] **Step 1: Branch**

Run: `git switch develop && git pull && git switch -c m1/s2-supply-chain`

- [ ] **Step 2: Write the guard with stubbed detectors**

File: `tests/meta/test_supply_chain.py` (stub)

```python
"""Supply-chain rules (spec §10.1). TDD stub: the helpers raise until implemented."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"


def workflow_files() -> list[Path]:
    raise NotImplementedError("workflow_files")


def uses_values(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    raise NotImplementedError("uses_values")


def dependabot() -> dict[str, Any]:
    raise NotImplementedError("dependabot")


def ecosystems_present() -> set[str]:
    raise NotImplementedError("ecosystems_present")


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    values = [v for f in workflow_files() for v in uses_values(yaml.safe_load(f.read_text()))]
    assert values


def test_every_pin_carries_its_release_version_as_a_comment() -> None:
    assert workflow_files()


def test_dependabot_covers_every_ecosystem_in_the_repo() -> None:
    assert ecosystems_present()


def test_every_dependabot_update_targets_develop_weekly() -> None:
    assert dependabot()


def test_sub_path_actions_are_grouped_above_the_patch_group() -> None:
    assert dependabot()
```

Run: `uv run pytest tests/meta/test_supply_chain.py`
Expected: 5 failed, each with `NotImplementedError` naming its helper.

- [ ] **Step 3: Implement the guard**

File: `tests/meta/test_supply_chain.py`

```python
"""Supply-chain rules (spec §10.1): pinned actions and a complete, develop-targeted Dependabot.

YAML is parsed, so a comment can never satisfy a rule. The one rule that is about comments
(the ``# vX.Y.Z`` after each pin) reads raw lines, and it cross-checks those lines against the
parsed values so that no ``uses`` can hide from it.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

PINNED = re.compile(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<value>\S+)(?P<tail>.*)$")
VERSION_COMMENT = re.compile(r"\s+# v\d+\.\d+\.\d+\s*")
SUB_PATH_PATTERN = re.compile(r"[\w.-]+/[\w.-]+\*")


def workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def uses_values(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from uses_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from uses_values(item)


def dependabot() -> dict[str, Any]:
    loaded = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def ecosystems_present() -> set[str]:
    present: set[str] = set()
    if (ROOT / "uv.lock").is_file():
        present.add("uv")
    if workflow_files():
        present.add("github-actions")
    return present


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    values = [
        value
        for path in workflow_files()
        for value in uses_values(yaml.safe_load(path.read_text(encoding="utf-8")))
    ]
    assert len(values) >= 8, values  # four CI jobs, each with checkout and setup-uv
    unpinned = [v for v in values if not v.startswith("./") and PINNED.fullmatch(v) is None]
    assert unpinned == []


def test_every_pin_carries_its_release_version_as_a_comment() -> None:
    parsed: list[str] = []
    raw: list[tuple[str, str]] = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        parsed.extend(uses_values(yaml.safe_load(text)))
        for line in text.splitlines():
            match = USES_LINE.match(line)
            if match is not None:
                raw.append((match["value"], match["tail"]))
    assert len(parsed) >= 8, parsed
    # Every parsed `uses` was seen on a line of its own, so none escapes the comment check.
    assert sorted(value for value, _ in raw) == sorted(parsed)
    missing = [
        value
        for value, tail in raw
        if not value.startswith("./") and VERSION_COMMENT.fullmatch(tail) is None
    ]
    assert missing == []


def test_dependabot_covers_every_ecosystem_in_the_repo() -> None:
    present = ecosystems_present()
    assert present == {"uv", "github-actions"}
    configured = {update["package-ecosystem"] for update in dependabot()["updates"]}
    assert present <= configured


def test_every_dependabot_update_targets_develop_weekly() -> None:
    updates = dependabot()["updates"]
    assert len(updates) >= 2
    wrong = [
        (u["package-ecosystem"], u.get("target-branch"), u.get("schedule", {}).get("interval"))
        for u in updates
        if u.get("target-branch") != "develop" or u.get("schedule", {}).get("interval") != "weekly"
    ]
    assert wrong == []


def test_sub_path_actions_are_grouped_above_the_patch_group() -> None:
    actions = next(u for u in dependabot()["updates"] if u["package-ecosystem"] == "github-actions")
    groups: dict[str, dict[str, Any]] = actions["groups"]
    names = list(groups)
    sub_path = [
        name
        for name in names
        if any(SUB_PATH_PATTERN.fullmatch(p) for p in groups[name].get("patterns", []))
    ]
    patch = [name for name in names if "patch" in groups[name].get("update-types", [])]
    assert sub_path, "no group gathers the sub-paths of one action repo"
    assert patch, "no patch group"
    # Dependabot puts an update in the first group that matches, so order matters.
    assert names.index(sub_path[0]) < names.index(patch[0])
```

- [ ] **Step 4: Run it and watch the Dependabot rules fail**

Run: `uv run pytest tests/meta/test_supply_chain.py`
Expected: 3 failed, 2 passed. The three Dependabot tests fail with `FileNotFoundError: ... .github/dependabot.yml`. Both workflow tests pass, because Task 1 already pinned every action with its comment. Step 7 proves those two tests can go red.

- [ ] **Step 5: Write the Dependabot config**

File: `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    target-branch: "develop"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"
    groups:
      python-minor-and-patch:
        update-types: ["minor", "patch"]

  - package-ecosystem: "github-actions"
    directory: "/"
    target-branch: "develop"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"
    groups:
      # Dependabot treats actions/cache, actions/cache/restore and actions/cache/save as
      # separate dependencies. This group moves every sub-path of one repo together. It must
      # stay above the patch group, because the first matching group wins.
      actions-cache:
        patterns: ["actions/cache*"]
      actions-patch:
        update-types: ["patch"]
```

- [ ] **Step 6: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
git add .github/dependabot.yml tests/meta/test_supply_chain.py
git commit -m "ci: Dependabot for uv and actions, and the supply-chain guard (S2)"
```
Expected: every test passes, coverage is 100%, and ruff and mypy are clean. Commit before step 7, so each mutation reverts to this commit.

- [ ] **Step 7: Mutation-verify each rule (predict, apply, check it applied, run the whole file, revert)**

Run each mutation on its own. Print the changed line to prove the mutation applied. Run the **whole** file, not a single test. Then revert with `git checkout -- <file>`, which is safe because step 6 committed.

| # | Mutation (leave every comment in place) | Predicted result |
|---|---|---|
| M1 | In `ci.yml`, change the first `actions/checkout@3d3c…b1` to `actions/checkout@v7` | `test_every_action_is_pinned…` fails and lists `actions/checkout@v7` |
| M2 | Delete ` # v7.0.1` from the first checkout line | `test_every_pin_carries…` fails and lists that value |
| M3 | Add a line `      # - uses: evil/action@main` under `steps:` of `lint` | Both workflow tests still pass: a comment is not a `uses` |
| M4 | In `dependabot.yml`, change the actions `target-branch` to `"main"` | `test_every_dependabot_update_targets_develop_weekly` fails |
| M5 | Move the `actions-cache` group below `actions-patch` | `test_sub_path_actions…` fails at the index assertion |
| M6 | Delete the `uv` update block, leaving its lines as comments | `test_dependabot_covers_every_ecosystem…` fails, and so does `test_every_dependabot_update_targets_develop_weekly` (its `len(updates) >= 2` liveness check) |

Record each mutation and its observed result in the PR body.

- [ ] **Step 8: Push, PR, verify, merge**

Ask Shyden to run `git push -u origin m1/s2-supply-chain`, and confirm it with `git ls-remote`. Open the PR into `develop` with `Refs #<S2 issue>` and follow **Merging a story**.

---

### Task 3: S3 Money

**Acceptance criteria (story text):**
1. `Money` holds an `int` amount of minor units plus a `Currency`. It refuses `float`, `bool`, `Decimal` and `str` amounts with a `TypeError` that names the type.
2. `IDR` is `Currency("IDR", 0)`. A currency code must be three capital letters, and `minor_units` must be an int from 0 to 4.
3. `+`, `-`, unary `-` and ordering work within one currency. Mixing currencies raises `CurrencyMismatchError("cannot combine IDR with USD")`. Non-`Money` operands give Python's standard `TypeError`.
4. `Money * int` (either side) multiplies exactly. Any other factor raises a `TypeError` that points to `times()`.
5. `times(rate: Decimal, rounding: Rounding)` is exact before its single explicit rounding, whatever the size of the amount. `Rounding.UP` rounds towards +∞ and `Rounding.DOWN` towards −∞. Non-finite or non-`Decimal` rates are refused.
6. `str(Money)` is `"IDR 1,500,000"`, `"IDR -1,500"` or `"USD 12.05"`.
7. 100% branch coverage. `float` is absent (enforced from Task 7).

**Files:**
- Create: `packages/steadyhand/src/steadyhand/money.py`
- Test: `tests/engine/test_money.py`

**Interfaces:**
- Consumes: nothing.
- Produces (`steadyhand.money`):
  - `class CurrencyMismatchError(ValueError)`, with `__init__(self, left: Currency, right: Currency)`.
  - `@dataclass(frozen=True, slots=True) class Currency: code: str; minor_units: int`
  - `IDR: Final[Currency]`, `MAX_MINOR_UNITS: Final = 4`
  - `class Rounding(Enum): UP, DOWN`
  - `@dataclass(frozen=True, slots=True) class Money: amount: int; currency: Currency`, with `zero(currency) -> Money`, `+ - neg`, `< <= > >=`, `* int`, `times(rate: Decimal, rounding: Rounding) -> Money` and `__str__`.

- [ ] **Step 1: Branch and write the stub**

Run: `git switch develop && git pull && git switch -c m1/s3-money`

File: `packages/steadyhand/src/steadyhand/money.py` (stub)

```python
"""Money in integer minor units. TDD stub: every behaviour raises until implemented."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum
from typing import Final

MAX_MINOR_UNITS: Final = 4


class CurrencyMismatchError(ValueError):
    def __init__(self, left: Currency, right: Currency) -> None:
        raise NotImplementedError("CurrencyMismatchError.__init__")


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    minor_units: int
    # No __post_init__ in the stub: the module-level IDR below must still import.


IDR: Final = Currency("IDR", 0)


class Rounding(Enum):
    UP = ROUND_CEILING
    DOWN = ROUND_FLOOR


@dataclass(frozen=True, slots=True)
class Money:
    amount: int
    currency: Currency

    def __post_init__(self) -> None:
        raise NotImplementedError("Money.__post_init__")

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        raise NotImplementedError("Money.zero")

    def __add__(self, other: Money) -> Money:
        raise NotImplementedError("Money.__add__")

    def __sub__(self, other: Money) -> Money:
        raise NotImplementedError("Money.__sub__")

    def __neg__(self) -> Money:
        raise NotImplementedError("Money.__neg__")

    def __mul__(self, quantity: int) -> Money:
        raise NotImplementedError("Money.__mul__")

    def __rmul__(self, quantity: int) -> Money:
        raise NotImplementedError("Money.__rmul__")

    def __lt__(self, other: Money) -> bool:
        raise NotImplementedError("Money.__lt__")

    def __le__(self, other: Money) -> bool:
        raise NotImplementedError("Money.__le__")

    def __gt__(self, other: Money) -> bool:
        raise NotImplementedError("Money.__gt__")

    def __ge__(self, other: Money) -> bool:
        raise NotImplementedError("Money.__ge__")

    def times(self, rate: Decimal, rounding: Rounding) -> Money:
        raise NotImplementedError("Money.times")

    def __str__(self) -> str:
        raise NotImplementedError("Money.__str__")
```

- [ ] **Step 2: Write the failing tests**

File: `tests/engine/test_money.py`

```python
"""Money: integer minor units, explicit rounding, no silent currency mixing."""

import operator
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money, Rounding


def usd() -> Currency:
    return Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


class TestCurrency:
    def test_idr_has_no_minor_unit(self) -> None:
        assert IDR.code == "IDR"
        assert IDR.minor_units == 0

    @pytest.mark.parametrize("code", ["idr", "ID", "IDRX", "", "I1R"])
    def test_code_must_be_three_capital_letters(self, code: str) -> None:
        with pytest.raises(ValueError, match="currency code must be three capital letters"):
            Currency(code, 0)

    def test_code_must_be_a_string(self) -> None:
        with pytest.raises(TypeError, match="currency code must be a str, got NoneType"):
            Currency(None, 0)  # type: ignore[arg-type]

    @pytest.mark.parametrize("minor_units", [-1, 5, True])
    def test_minor_units_must_be_an_int_from_0_to_4(self, minor_units: int) -> None:
        with pytest.raises(ValueError, match="minor_units must be an int from 0 to 4"):
            Currency("USD", minor_units)

    @pytest.mark.parametrize("minor_units", [0, 4])
    def test_minor_units_boundaries_are_accepted(self, minor_units: int) -> None:
        assert Currency("XTS", minor_units).minor_units == minor_units


class TestConstruction:
    @pytest.mark.parametrize("amount", [Decimal(1), True, "1", 1.0])
    def test_amount_must_be_an_int(self, amount: object) -> None:
        with pytest.raises(TypeError, match="Money amount must be an int of minor units, got"):
            Money(amount, IDR)  # type: ignore[arg-type]

    def test_currency_must_be_a_currency(self) -> None:
        with pytest.raises(TypeError, match="Money currency must be a Currency, got str"):
            Money(1, "IDR")  # type: ignore[arg-type]

    def test_zero(self) -> None:
        assert Money.zero(usd()) == Money(0, usd())

    def test_equality_and_hash_include_the_currency(self) -> None:
        assert Money(0, IDR) != Money(0, usd())
        assert hash(rp(5)) == hash(rp(5))


class TestArithmetic:
    def test_add_subtract_negate(self) -> None:
        assert rp(7) + rp(5) == rp(12)
        assert rp(7) - rp(12) == rp(-5)
        assert -rp(7) == rp(-7)

    @pytest.mark.parametrize("name", ["add", "sub", "lt", "le", "gt", "ge"])
    def test_mixing_currencies_raises(self, name: str) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            getattr(operator, name)(rp(1), Money(1, usd()))

    @pytest.mark.parametrize(
        ("name", "message"),
        [
            ("add", r"unsupported operand type\(s\) for \+"),
            ("sub", r"unsupported operand type\(s\) for -"),
            ("lt", "'<' not supported"),
            ("le", "'<=' not supported"),
            ("gt", "'>' not supported"),
            ("ge", "'>=' not supported"),
        ],
    )
    def test_non_money_operands_are_refused(self, name: str, message: str) -> None:
        with pytest.raises(TypeError, match=message):
            getattr(operator, name)(rp(1), 1)

    def test_ordering(self) -> None:
        assert rp(1) < rp(2)
        assert rp(2) <= rp(2)
        assert rp(3) > rp(2)
        assert rp(2) >= rp(2)
        assert not rp(2) < rp(2)
        assert not rp(2) > rp(2)

    def test_multiply_by_a_share_count_on_either_side(self) -> None:
        assert rp(4_150) * 300 == rp(1_245_000)
        assert 300 * rp(4_150) == rp(1_245_000)

    @pytest.mark.parametrize("factor", [Decimal("1.5"), True, 1.5])
    def test_multiply_refuses_anything_but_an_int(self, factor: object) -> None:
        with pytest.raises(TypeError, match=r"multiply Money by an int quantity, got .*use times"):
            _ = rp(10) * factor  # type: ignore[operator]


class TestTimes:
    def test_rounds_up_for_what_you_pay(self) -> None:
        # A 0.15% fee on Rp 1,000,001 is Rp 1,500.0015 before rounding.
        assert rp(1_000_001).times(Decimal("0.0015"), Rounding.UP) == rp(1_501)

    def test_rounds_down_for_what_you_receive(self) -> None:
        assert rp(1_000_001).times(Decimal("0.0015"), Rounding.DOWN) == rp(1_500)

    def test_exact_results_are_not_moved(self) -> None:
        assert rp(1_000_000).times(Decimal("0.001"), Rounding.UP) == rp(1_000)
        assert rp(1_000_000).times(Decimal("0.001"), Rounding.DOWN) == rp(1_000)

    def test_direction_is_by_value_not_by_magnitude(self) -> None:
        assert rp(-3).times(Decimal("0.5"), Rounding.UP) == rp(-1)
        assert rp(-3).times(Decimal("0.5"), Rounding.DOWN) == rp(-2)

    def test_huge_amounts_are_exact(self) -> None:
        # 29+ significant digits: Decimal's default 28-digit context would drop the 0.0015.
        amount = 10**40 + 1
        assert rp(amount).times(Decimal("0.0015"), Rounding.UP) == rp(15 * 10**36 + 1)
        assert rp(amount).times(Decimal("0.0015"), Rounding.DOWN) == rp(15 * 10**36)

    @pytest.mark.parametrize("rate", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_rate_must_be_finite(self, rate: Decimal) -> None:
        with pytest.raises(ValueError, match="rate must be finite"):
            rp(1).times(rate, Rounding.UP)

    def test_rate_must_be_a_decimal(self) -> None:
        with pytest.raises(TypeError, match="rate must be a Decimal, got int"):
            rp(1).times(1, Rounding.UP)  # type: ignore[arg-type]

    @given(
        amount=st.integers(min_value=0, max_value=10**15),
        rate=st.decimals(min_value=0, max_value=1, places=6, allow_nan=False, allow_infinity=False),
    )
    def test_up_and_down_bracket_the_exact_value(self, amount: int, rate: Decimal) -> None:
        up = rp(amount).times(rate, Rounding.UP)
        down = rp(amount).times(rate, Rounding.DOWN)
        exact = amount * rate
        assert down.amount <= exact <= up.amount
        assert up.amount - down.amount <= 1


class TestFormatting:
    @pytest.mark.parametrize(
        ("amount", "code", "minor_units", "text"),
        [
            (1_500_000, "IDR", 0, "IDR 1,500,000"),
            (-1_500, "IDR", 0, "IDR -1,500"),
            (0, "IDR", 0, "IDR 0"),
            (1_205, "USD", 2, "USD 12.05"),
            (-5, "USD", 2, "USD -0.05"),
        ],
    )
    def test_str(self, amount: int, code: str, minor_units: int, text: str) -> None:
        assert str(Money(amount, Currency(code, minor_units))) == text
```

Parametrize values are raw numbers and strings, never `Money`. A `Money` built at collection time would raise from the stub while pytest collects, error the whole file, and hide every individual failure.

- [ ] **Step 3: Run against the stub**

Run: `uv run pytest tests/engine/test_money.py`
Expected: the file collects. Every test fails with `NotImplementedError` or `Failed: DID NOT RAISE`, except these, which pass against the stub for the reason given:
- `test_idr_has_no_minor_unit`: it pins data, not behaviour.
- `test_minor_units_boundaries_are_accepted[0]` and `[4]`: the stub accepts every currency.

- [ ] **Step 4: Implement**

File: `packages/steadyhand/src/steadyhand/money.py`

```python
"""Money in integer minor units, with explicit rounding.

``float`` never appears in this module (a meta-guard enforces it): a float cannot hold most
decimal amounts exactly, and a trading simulation that drifts by a rupiah a day is wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, Inexact, localcontext
from enum import Enum
from typing import Final

MAX_MINOR_UNITS: Final = 4
_CURRENCY_CODE = re.compile(r"[A-Z]{3}")


class CurrencyMismatchError(ValueError):
    """Two amounts in different currencies were combined or compared."""

    def __init__(self, left: Currency, right: Currency) -> None:
        super().__init__(f"cannot combine {left.code} with {right.code}")


@dataclass(frozen=True, slots=True)
class Currency:
    """An ISO 4217 currency and the number of decimal places in its minor unit."""

    code: str
    minor_units: int

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            msg = f"currency code must be a str, got {type(self.code).__name__}"
            raise TypeError(msg)
        if _CURRENCY_CODE.fullmatch(self.code) is None:
            msg = f"currency code must be three capital letters, got {self.code!r}"
            raise ValueError(msg)
        if type(self.minor_units) is not int or not 0 <= self.minor_units <= MAX_MINOR_UNITS:
            msg = (
                f"minor_units must be an int from 0 to {MAX_MINOR_UNITS}, got {self.minor_units!r}"
            )
            raise ValueError(msg)


IDR: Final = Currency("IDR", 0)
"""Indonesian rupiah. It has no minor unit in practical use, so one unit is one rupiah."""


class Rounding(Enum):
    """Which way a rate calculation rounds to a whole minor unit."""

    UP = ROUND_CEILING
    """Towards positive infinity. Use it for what you pay: costs and buy prices."""
    DOWN = ROUND_FLOOR
    """Towards negative infinity. Use it for what you receive: proceeds and dividends."""


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount: an ``int`` of minor units plus its currency."""

    amount: int
    currency: Currency

    def __post_init__(self) -> None:
        if type(self.amount) is not int:
            msg = f"Money amount must be an int of minor units, got {type(self.amount).__name__}"
            raise TypeError(msg)
        if not isinstance(self.currency, Currency):
            msg = f"Money currency must be a Currency, got {type(self.currency).__name__}"
            raise TypeError(msg)

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        return cls(0, currency)

    def _require_same_currency(self, other: Money) -> None:
        if other.currency != self.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, quantity: int) -> Money:
        if type(quantity) is not int:
            msg = (
                f"multiply Money by an int quantity, got {type(quantity).__name__}; "
                "use times() for a rate"
            )
            raise TypeError(msg)
        return Money(self.amount * quantity, self.currency)

    def __rmul__(self, quantity: int) -> Money:
        return self * quantity

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self.amount >= other.amount

    def times(self, rate: Decimal, rounding: Rounding) -> Money:
        """Multiply by *rate* exactly, then round once to a whole minor unit."""
        if not isinstance(rate, Decimal):
            msg = f"rate must be a Decimal, got {type(rate).__name__}"
            raise TypeError(msg)
        if not rate.is_finite():
            msg = f"rate must be finite, got {rate}"
            raise ValueError(msg)
        # A product has at most as many digits as its two factors together. Giving the context
        # that much precision makes the multiplication exact, and trapping Inexact makes any
        # future mistake in this sum fail loudly instead of rounding twice.
        digits = len(str(abs(self.amount))) + len(rate.as_tuple().digits)
        with localcontext() as context:
            context.prec = digits + 1
            context.traps[Inexact] = True
            whole = (Decimal(self.amount) * rate).to_integral_value(rounding=rounding.value)
        return Money(int(whole), self.currency)

    def __str__(self) -> str:
        sign = "-" if self.amount < 0 else ""
        places = self.currency.minor_units
        units, minor = divmod(abs(self.amount), 10**places)
        if places == 0:
            return f"{self.currency.code} {sign}{units:,}"
        return f"{self.currency.code} {sign}{units:,}.{minor:0{places}d}"
```

- [ ] **Step 5: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
```
Expected: all pass, 100% branch coverage including `money.py`, and ruff and mypy are clean.

- [ ] **Step 6: Commit, push, PR, verify, merge**

```bash
git add packages/steadyhand/src/steadyhand/money.py tests/engine/test_money.py
git commit -m "feat(engine): Money in integer minor units with explicit rounding (S3)"
```
Ask Shyden to run `git push -u origin m1/s3-money`, and confirm with `git ls-remote`. Open the PR with `Refs #<S3 issue>` and follow **Merging a story**.

---

### Task 4: S4 Trading value types

**Acceptance criteria (story text):**
1. `Instrument(symbol, market, currency)` validates its symbol (1–20 of `A-Z 0-9 . -`, starting with a letter or digit) and its market (2–10 capital letters). A non-string symbol or market is a `TypeError`, and a malformed one is a `ValueError`.
2. `Bar` holds **unadjusted** OHLC `Money` plus an `int` volume. It raises `InvalidBarError`, naming the ticker, the date and the field, when a price is in the wrong currency, a price is not positive, the volume is negative or not an int, or low/high do not bracket open/close. A zero-volume bar is valid.
3. `Split(old_shares, new_shares)`, `CashDividend(per_share: Decimal)` in major units (fractional allowed) and `OtherAction(description)` validate themselves. `CorporateAction` is their union.
4. `Order`, `OrderAck` (a rejection must carry a reason), `Costs` (non-negative, one currency, `total`), `Fill` (dated on or after its order, 1 ≤ quantity ≤ ordered, price positive and in the instrument's currency, `gross`) and `Position` (quantity ≥ 1, cost basis ≥ 0 and in the instrument's currency).
5. Every date field refuses a `datetime`, and every count refuses a `bool`, each with a `TypeError` that names the field.
6. 100% branch coverage.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/_validate.py`, `packages/steadyhand/src/steadyhand/types.py`
- Test: `tests/engine/test_validate.py`, `tests/engine/test_types.py`

**Interfaces:**
- Consumes: `Money`, `Currency`, `IDR`, `CurrencyMismatchError` from `steadyhand.money` (Task 3).
- Produces:
  - `steadyhand._validate`: `require_date(value: object, what: str) -> None` and `require_int(value: object, what: str, *, minimum: int) -> None`.
  - `steadyhand.types`: `Side(Enum)` with `BUY`/`SELL`, `Instrument`, `InvalidBarError(ValueError)`, `Bar`, `Split`, `CashDividend`, `OtherAction`, `type CorporateAction = Split | CashDividend | OtherAction`, `Order`, `OrderAck`, `Costs` (`zero(currency)`, `total`), `Fill` (`gross`) and `Position`. The field names and orders are exactly as in step 4.

- [ ] **Step 1: Branch and write the stubs**

Run: `git switch develop && git pull && git switch -c m1/s4-types`

File: `packages/steadyhand/src/steadyhand/_validate.py` (stub)

```python
"""Shared argument checks. TDD stub."""


def require_date(value: object, what: str) -> None:
    raise NotImplementedError("require_date")


def require_int(value: object, what: str, *, minimum: int) -> None:
    raise NotImplementedError("require_int")
```

File: `packages/steadyhand/src/steadyhand/types.py` (stub)

```python
"""Market-neutral value types. TDD stub: every constructor raises until implemented."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from steadyhand.money import Currency, Money


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    market: str
    currency: Currency

    def __post_init__(self) -> None:
        raise NotImplementedError("Instrument.__post_init__")


class InvalidBarError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Bar:
    instrument: Instrument
    day: date
    open: Money
    high: Money
    low: Money
    close: Money
    volume: int

    def __post_init__(self) -> None:
        raise NotImplementedError("Bar.__post_init__")


@dataclass(frozen=True, slots=True)
class Split:
    instrument: Instrument
    ex_date: date
    old_shares: int
    new_shares: int

    def __post_init__(self) -> None:
        raise NotImplementedError("Split.__post_init__")


@dataclass(frozen=True, slots=True)
class CashDividend:
    instrument: Instrument
    ex_date: date
    per_share: Decimal

    def __post_init__(self) -> None:
        raise NotImplementedError("CashDividend.__post_init__")


@dataclass(frozen=True, slots=True)
class OtherAction:
    instrument: Instrument
    ex_date: date
    description: str

    def __post_init__(self) -> None:
        raise NotImplementedError("OtherAction.__post_init__")


type CorporateAction = Split | CashDividend | OtherAction


@dataclass(frozen=True, slots=True)
class Order:
    instrument: Instrument
    side: Side
    quantity: int
    placed_on: date

    def __post_init__(self) -> None:
        raise NotImplementedError("Order.__post_init__")


@dataclass(frozen=True, slots=True)
class OrderAck:
    order: Order
    accepted: bool
    reason: str = ""

    def __post_init__(self) -> None:
        raise NotImplementedError("OrderAck.__post_init__")


@dataclass(frozen=True, slots=True)
class Costs:
    fee: Money
    levy: Money
    tax: Money

    def __post_init__(self) -> None:
        raise NotImplementedError("Costs.__post_init__")

    @classmethod
    def zero(cls, currency: Currency) -> Costs:
        raise NotImplementedError("Costs.zero")

    @property
    def total(self) -> Money:
        raise NotImplementedError("Costs.total")


@dataclass(frozen=True, slots=True)
class Fill:
    order: Order
    day: date
    quantity: int
    price: Money
    costs: Costs

    def __post_init__(self) -> None:
        raise NotImplementedError("Fill.__post_init__")

    @property
    def gross(self) -> Money:
        raise NotImplementedError("Fill.gross")


@dataclass(frozen=True, slots=True)
class Position:
    instrument: Instrument
    quantity: int
    cost_basis: Money

    def __post_init__(self) -> None:
        raise NotImplementedError("Position.__post_init__")
```

- [ ] **Step 2: Write the failing tests**

Every test builds its values inside the test, never at module level: a module-level `Instrument(...)` would raise from the stub during collection and hide every individual failure.

File: `tests/engine/test_validate.py`

```python
"""The shared checks refuse the look-alike types that Python's subclassing lets through."""

from datetime import UTC, date, datetime

import pytest

from steadyhand._validate import require_date, require_int


def test_require_date_accepts_a_date() -> None:
    require_date(date(2026, 1, 5), "day")


def test_require_date_refuses_a_datetime() -> None:
    with pytest.raises(TypeError, match="day must be a date, got datetime"):
        require_date(datetime(2026, 1, 5, tzinfo=UTC), "day")


def test_require_date_refuses_a_string() -> None:
    with pytest.raises(TypeError, match="day must be a date, got str"):
        require_date("2026-01-05", "day")


def test_require_int_accepts_the_minimum() -> None:
    require_int(1, "quantity", minimum=1)


def test_require_int_refuses_one_below_the_minimum() -> None:
    with pytest.raises(ValueError, match="quantity must be at least 1, got 0"):
        require_int(0, "quantity", minimum=1)


@pytest.mark.parametrize(("value", "name"), [(True, "bool"), ("1", "str"), (None, "NoneType")])
def test_require_int_refuses_non_ints(value: object, name: str) -> None:
    with pytest.raises(TypeError, match=f"quantity must be an int, got {name}"):
        require_int(value, "quantity", minimum=1)
```

File: `tests/engine/test_types.py`

```python
"""Value types validate themselves on construction, so bad data fails where it enters."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import (
    Bar,
    CashDividend,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)

DAY = date(2026, 1, 5)


def usd() -> Currency:
    return Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bbri() -> Instrument:
    return Instrument("BBRI", "IDX", IDR)


def bar(**overrides: object) -> Bar:
    fields: dict[str, object] = {
        "instrument": bbri(),
        "day": DAY,
        "open": rp(4_100),
        "high": rp(4_200),
        "low": rp(4_000),
        "close": rp(4_150),
        "volume": 1_000_000,
    }
    fields.update(overrides)
    return Bar(**fields)  # type: ignore[arg-type]


def order(side: Side = Side.BUY, quantity: int = 300) -> Order:
    return Order(bbri(), side, quantity, DAY)


def costs(fee: int = 0, levy: int = 0, tax: int = 0) -> Costs:
    return Costs(rp(fee), rp(levy), rp(tax))


def test_side_values() -> None:
    assert [side.value for side in Side] == ["buy", "sell"]


class TestInstrument:
    @pytest.mark.parametrize("symbol", ["BBRI", "BRK.B", "0700", "A", "X" * 20, "BF-B"])
    def test_accepts_exchange_symbols(self, symbol: str) -> None:
        assert Instrument(symbol, "IDX", IDR).symbol == symbol

    @pytest.mark.parametrize("symbol", ["", "bbri", "BB RI", ".BBRI", "X" * 21])
    def test_refuses_malformed_symbols(self, symbol: str) -> None:
        with pytest.raises(ValueError, match="symbol must be 1-20 capital letters"):
            Instrument(symbol, "IDX", IDR)

    def test_refuses_a_non_string_symbol(self) -> None:
        with pytest.raises(TypeError, match="symbol must be a str, got NoneType"):
            Instrument(None, "IDX", IDR)  # type: ignore[arg-type]

    def test_refuses_a_non_string_market(self) -> None:
        with pytest.raises(TypeError, match="market must be a str, got int"):
            Instrument("BBRI", 1, IDR)  # type: ignore[arg-type]

    @pytest.mark.parametrize("market", ["I", "idx", "IDX1", "M" * 11])
    def test_refuses_malformed_markets(self, market: str) -> None:
        with pytest.raises(ValueError, match="market must be 2-10 capital letters"):
            Instrument("BBRI", market, IDR)

    @pytest.mark.parametrize("market", ["US", "M" * 10])
    def test_market_length_boundaries_are_accepted(self, market: str) -> None:
        assert Instrument("BBRI", market, IDR).market == market

    def test_is_compared_and_hashed_by_value(self) -> None:
        assert {bbri(): 1}[Instrument("BBRI", "IDX", IDR)] == 1


class TestBar:
    def test_a_consistent_bar_is_accepted(self) -> None:
        assert bar().close == rp(4_150)

    def test_zero_volume_is_a_valid_bar(self) -> None:
        # A suspended stock's day: the bar is real data; the fill model rejects orders on it.
        assert bar(volume=0).volume == 0

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_prices_must_be_positive(self, field: str) -> None:
        with pytest.raises(
            InvalidBarError, match=f"BBRI 2026-01-05: {field} must be positive, got IDR 0"
        ):
            bar(**{field: rp(0)})

    def test_prices_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(InvalidBarError, match="BBRI 2026-01-05: close is in USD, expected IDR"):
            bar(close=Money(415_000, usd()))

    @pytest.mark.parametrize("volume", [-1, True, "1"])
    def test_volume_must_be_a_non_negative_int(self, volume: object) -> None:
        with pytest.raises(InvalidBarError, match="volume must be a non-negative int"):
            bar(volume=volume)

    @pytest.mark.parametrize(("field", "amount"), [("high", 4_150), ("low", 4_100)])
    def test_high_and_low_may_touch_open_or_close(self, field: str, amount: int) -> None:
        assert bar(**{field: rp(amount)}).volume == 1_000_000

    @pytest.mark.parametrize(("field", "amount"), [("high", 4_149), ("low", 4_101)])
    def test_high_and_low_must_bracket_open_and_close(self, field: str, amount: int) -> None:
        with pytest.raises(InvalidBarError, match="do not bracket open IDR 4,100 and close"):
            bar(**{field: rp(amount)})

    def test_day_must_be_a_plain_date(self) -> None:
        with pytest.raises(TypeError, match="bar day must be a date, got datetime"):
            bar(day=datetime(2026, 1, 5, tzinfo=UTC))


class TestCorporateActions:
    @pytest.mark.parametrize(("old", "new"), [(1, 5), (5, 1)])
    def test_splits_and_reverse_splits(self, old: int, new: int) -> None:
        split = Split(bbri(), DAY, old, new)
        assert (split.old_shares, split.new_shares) == (old, new)

    def test_a_split_must_change_the_share_count(self) -> None:
        with pytest.raises(ValueError, match="BBRI 2026-01-05: turning 2 shares into 2"):
            Split(bbri(), DAY, 2, 2)

    def test_split_counts_must_be_at_least_one(self) -> None:
        with pytest.raises(ValueError, match="old_shares must be at least 1, got 0"):
            Split(bbri(), DAY, 0, 1)

    def test_split_counts_refuse_bool(self) -> None:
        with pytest.raises(TypeError, match="new_shares must be an int, got bool"):
            Split(bbri(), DAY, 1, True)

    def test_split_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="split ex_date must be a date"):
            Split(bbri(), datetime(2026, 1, 5, tzinfo=UTC), 1, 2)

    def test_fractional_dividends_are_allowed(self) -> None:
        assert CashDividend(bbri(), DAY, Decimal("12.5")).per_share == Decimal("12.5")

    @pytest.mark.parametrize("per_share", [Decimal(0), Decimal(-1), Decimal("NaN")])
    def test_dividend_must_be_positive_and_finite(self, per_share: Decimal) -> None:
        with pytest.raises(ValueError, match="per_share must be a positive finite Decimal"):
            CashDividend(bbri(), DAY, per_share)

    def test_dividend_per_share_must_be_a_decimal(self) -> None:
        with pytest.raises(TypeError, match="per_share must be a Decimal, got int"):
            CashDividend(bbri(), DAY, 12)  # type: ignore[arg-type]

    def test_dividend_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="dividend ex_date must be a date"):
            CashDividend(bbri(), datetime(2026, 1, 5, tzinfo=UTC), Decimal(1))

    def test_other_action_needs_a_description(self) -> None:
        with pytest.raises(
            ValueError, match="BBRI 2026-01-05: an other action needs a description"
        ):
            OtherAction(bbri(), DAY, "  ")

    def test_other_action_keeps_its_description(self) -> None:
        assert OtherAction(bbri(), DAY, "rights issue 1:4").description == "rights issue 1:4"

    def test_other_action_ex_date_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="action ex_date must be a date"):
            OtherAction(bbri(), datetime(2026, 1, 5, tzinfo=UTC), "merger")


class TestOrders:
    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="order quantity must be at least 1, got 0"):
            order(quantity=0)

    def test_quantity_refuses_bool(self) -> None:
        with pytest.raises(TypeError, match="order quantity must be an int, got bool"):
            order(quantity=True)

    def test_placed_on_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="placed_on must be a date"):
            Order(bbri(), Side.BUY, 1, datetime(2026, 1, 5, tzinfo=UTC))

    def test_a_rejection_must_say_why(self) -> None:
        with pytest.raises(ValueError, match="a rejected buy order for BBRI must say why"):
            OrderAck(order(), accepted=False, reason=" ")

    def test_a_rejection_with_a_reason_is_accepted(self) -> None:
        ack = OrderAck(order(), accepted=False, reason="outside the auto-reject band")
        assert ack.reason == "outside the auto-reject band"

    def test_an_acceptance_needs_no_reason(self) -> None:
        assert OrderAck(order(), accepted=True).reason == ""


class TestCosts:
    def test_total_adds_the_three_parts(self) -> None:
        assert costs(fee=450, levy=30, tax=100).total == rp(580)

    def test_zero(self) -> None:
        assert Costs.zero(IDR) == costs()

    @pytest.mark.parametrize("part", ["fee", "levy", "tax"])
    def test_no_part_may_be_negative(self, part: str) -> None:
        with pytest.raises(ValueError, match=f"{part} cannot be negative, got IDR -1"):
            costs(**{part: -1})

    def test_parts_must_share_a_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Costs(rp(1), rp(1), Money(1, usd()))


class TestFill:
    def test_gross_is_price_times_quantity(self) -> None:
        fill = Fill(order(), DAY, 300, rp(4_150), costs())
        assert fill.gross == rp(1_245_000)

    def test_a_partial_fill_is_allowed(self) -> None:
        assert Fill(order(), DAY, 100, rp(4_150), costs()).quantity == 100

    def test_cannot_precede_its_order(self) -> None:
        with pytest.raises(ValueError, match="a fill on 2026-01-04 cannot precede its order"):
            Fill(order(), date(2026, 1, 4), 300, rp(4_150), costs())

    def test_day_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="fill day must be a date"):
            Fill(order(), datetime(2026, 1, 5, tzinfo=UTC), 300, rp(4_150), costs())

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="fill quantity must be at least 1, got 0"):
            Fill(order(), DAY, 0, rp(4_150), costs())

    def test_cannot_exceed_the_order(self) -> None:
        with pytest.raises(ValueError, match="filled 301 shares but the order was for 300"):
            Fill(order(), DAY, 301, rp(4_150), costs())

    def test_price_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Fill(order(), DAY, 300, Money(4_150, usd()), costs())

    def test_costs_must_be_in_the_instrument_currency(self) -> None:
        usd_costs = Costs(Money(0, usd()), Money(0, usd()), Money(0, usd()))
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Fill(order(), DAY, 300, rp(4_150), usd_costs)

    def test_price_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="fill price must be positive, got IDR 0"):
            Fill(order(), DAY, 300, rp(0), costs())


class TestPosition:
    def test_holds_quantity_and_cost_basis(self) -> None:
        position = Position(bbri(), 300, rp(1_245_450))
        assert (position.quantity, position.cost_basis) == (300, rp(1_245_450))

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="position quantity must be at least 1, got 0"):
            Position(bbri(), 0, rp(0))

    def test_cost_basis_must_be_in_the_instrument_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Position(bbri(), 1, Money(1, usd()))

    def test_cost_basis_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError, match="cost basis cannot be negative, got IDR -1"):
            Position(bbri(), 1, rp(-1))
```

- [ ] **Step 3: Run against the stubs**

Run: `uv run pytest tests/engine/test_validate.py tests/engine/test_types.py`
Expected: every test fails (`NotImplementedError: require_date`, `...Instrument.__post_init__` and so on) except `test_side_values`, which pins data. Both files collect.

- [ ] **Step 4: Implement**

File: `packages/steadyhand/src/steadyhand/_validate.py`

```python
"""Shared argument checks for the engine's value types.

Two Python subclass relationships let wrong values through a plain ``isinstance``: ``bool`` is
an ``int``, and ``datetime`` is a ``date``. Both are refused here, at the point of entry.
"""

from datetime import date, datetime


def require_date(value: object, what: str) -> None:
    """Raise ``TypeError`` unless *value* is a plain ``date``."""
    if isinstance(value, datetime) or not isinstance(value, date):
        msg = f"{what} must be a date, got {type(value).__name__}"
        raise TypeError(msg)


def require_int(value: object, what: str, *, minimum: int) -> None:
    """Raise unless *value* is an ``int`` (never a ``bool``) of at least *minimum*."""
    if type(value) is not int:
        msg = f"{what} must be an int, got {type(value).__name__}"
        raise TypeError(msg)
    if value < minimum:
        msg = f"{what} must be at least {minimum}, got {value}"
        raise ValueError(msg)
```

File: `packages/steadyhand/src/steadyhand/types.py`

```python
"""Market-neutral value types: instruments, bars, corporate actions, orders, fills, positions.

Every type validates itself when constructed, so bad data fails where it enters rather than
three steps later. Lot sizes, ticks and price bands are market rules, not type rules: they live
in a ``MarketRules`` implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from steadyhand._validate import require_date, require_int
from steadyhand.money import Currency, CurrencyMismatchError, Money

_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,19}")
_MARKET = re.compile(r"[A-Z]{2,10}")


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Instrument:
    """A tradable stock: its exchange symbol (``BBRI``), market (``IDX``) and currency."""

    symbol: str
    market: str
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            msg = f"symbol must be a str, got {type(self.symbol).__name__}"
            raise TypeError(msg)
        if _SYMBOL.fullmatch(self.symbol) is None:
            msg = (
                f"symbol must be 1-20 capital letters, digits, dots or dashes, got {self.symbol!r}"
            )
            raise ValueError(msg)
        if not isinstance(self.market, str):
            msg = f"market must be a str, got {type(self.market).__name__}"
            raise TypeError(msg)
        if _MARKET.fullmatch(self.market) is None:
            msg = f"market must be 2-10 capital letters, got {self.market!r}"
            raise ValueError(msg)


class InvalidBarError(ValueError):
    """A price bar is inconsistent. It must never reach the cache or a strategy."""


@dataclass(frozen=True, slots=True)
class Bar:
    """One trading day of **unadjusted** prices for one instrument (spec §4.3)."""

    instrument: Instrument
    day: date
    open: Money
    high: Money
    low: Money
    close: Money
    volume: int

    def __post_init__(self) -> None:
        require_date(self.day, "bar day")
        where = f"{self.instrument.symbol} {self.day.isoformat()}"
        expected = self.instrument.currency
        prices = {"open": self.open, "high": self.high, "low": self.low, "close": self.close}
        for name, price in prices.items():
            if price.currency != expected:
                msg = f"{where}: {name} is in {price.currency.code}, expected {expected.code}"
                raise InvalidBarError(msg)
            if price.amount <= 0:
                msg = f"{where}: {name} must be positive, got {price}"
                raise InvalidBarError(msg)
        if type(self.volume) is not int or self.volume < 0:
            msg = f"{where}: volume must be a non-negative int, got {self.volume!r}"
            raise InvalidBarError(msg)
        bracketed = self.low <= self.open <= self.high and self.low <= self.close <= self.high
        if not bracketed:
            msg = (
                f"{where}: low {self.low} and high {self.high} do not bracket "
                f"open {self.open} and close {self.close}"
            )
            raise InvalidBarError(msg)


@dataclass(frozen=True, slots=True)
class Split:
    """On ``ex_date``, every ``old_shares`` become ``new_shares``.

    A 5-for-1 split is ``Split(instrument, ex_date, 1, 5)``; a 1-for-5 reverse split is ``5, 1``.
    """

    instrument: Instrument
    ex_date: date
    old_shares: int
    new_shares: int

    def __post_init__(self) -> None:
        require_date(self.ex_date, "split ex_date")
        require_int(self.old_shares, "old_shares", minimum=1)
        require_int(self.new_shares, "new_shares", minimum=1)
        if self.old_shares == self.new_shares:
            msg = (
                f"{self.instrument.symbol} {self.ex_date.isoformat()}: turning "
                f"{self.old_shares} shares into {self.new_shares} changes nothing"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CashDividend:
    """A cash dividend for holders before ``ex_date``.

    ``per_share`` is in major units of the instrument's currency and may be fractional
    (Rp 12.5 a share), so it is a ``Decimal``, not ``Money``.
    """

    instrument: Instrument
    ex_date: date
    per_share: Decimal

    def __post_init__(self) -> None:
        require_date(self.ex_date, "dividend ex_date")
        if not isinstance(self.per_share, Decimal):
            msg = f"per_share must be a Decimal, got {type(self.per_share).__name__}"
            raise TypeError(msg)
        if not self.per_share.is_finite() or self.per_share <= 0:
            msg = f"per_share must be a positive finite Decimal, got {self.per_share}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OtherAction:
    """Any other corporate action (a rights issue, a merger). The engine freezes the stock."""

    instrument: Instrument
    ex_date: date
    description: str

    def __post_init__(self) -> None:
        require_date(self.ex_date, "action ex_date")
        if not self.description.strip():
            msg = (
                f"{self.instrument.symbol} {self.ex_date.isoformat()}: "
                "an other action needs a description"
            )
            raise ValueError(msg)


type CorporateAction = Split | CashDividend | OtherAction


@dataclass(frozen=True, slots=True)
class Order:
    """A request to trade ``quantity`` shares, placed on ``placed_on``."""

    instrument: Instrument
    side: Side
    quantity: int
    placed_on: date

    def __post_init__(self) -> None:
        require_int(self.quantity, "order quantity", minimum=1)
        require_date(self.placed_on, "placed_on")


@dataclass(frozen=True, slots=True)
class OrderAck:
    """A broker's answer to one submitted order. A rejection always says why."""

    order: Order
    accepted: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.accepted and not self.reason.strip():
            msg = (
                f"a rejected {self.order.side.value} order for "
                f"{self.order.instrument.symbol} must say why"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Costs:
    """What one trade costs on top of its gross value: broker fee, exchange levy, sell tax."""

    fee: Money
    levy: Money
    tax: Money

    def __post_init__(self) -> None:
        for name, part in (("fee", self.fee), ("levy", self.levy), ("tax", self.tax)):
            if part.currency != self.fee.currency:
                raise CurrencyMismatchError(self.fee.currency, part.currency)
            if part.amount < 0:
                msg = f"{name} cannot be negative, got {part}"
                raise ValueError(msg)

    @classmethod
    def zero(cls, currency: Currency) -> Costs:
        nothing = Money.zero(currency)
        return cls(nothing, nothing, nothing)

    @property
    def total(self) -> Money:
        return self.fee + self.levy + self.tax


@dataclass(frozen=True, slots=True)
class Fill:
    """An order, or part of one, that traded on ``day`` at ``price``."""

    order: Order
    day: date
    quantity: int
    price: Money
    costs: Costs

    def __post_init__(self) -> None:
        require_date(self.day, "fill day")
        if self.day < self.order.placed_on:
            msg = (
                f"a fill on {self.day.isoformat()} cannot precede its order placed on "
                f"{self.order.placed_on.isoformat()}"
            )
            raise ValueError(msg)
        require_int(self.quantity, "fill quantity", minimum=1)
        if self.quantity > self.order.quantity:
            msg = f"filled {self.quantity} shares but the order was for {self.order.quantity}"
            raise ValueError(msg)
        currency = self.order.instrument.currency
        if self.price.currency != currency:
            raise CurrencyMismatchError(currency, self.price.currency)
        if self.costs.fee.currency != currency:
            raise CurrencyMismatchError(currency, self.costs.fee.currency)
        if self.price.amount <= 0:
            msg = f"fill price must be positive, got {self.price}"
            raise ValueError(msg)

    @property
    def gross(self) -> Money:
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class Position:
    """Shares held in one instrument. ``cost_basis`` is what they cost, buy costs included."""

    instrument: Instrument
    quantity: int
    cost_basis: Money

    def __post_init__(self) -> None:
        require_int(self.quantity, "position quantity", minimum=1)
        if self.cost_basis.currency != self.instrument.currency:
            raise CurrencyMismatchError(self.instrument.currency, self.cost_basis.currency)
        if self.cost_basis.amount < 0:
            msg = f"cost basis cannot be negative, got {self.cost_basis}"
            raise ValueError(msg)
```

- [ ] **Step 5: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
```
Expected: all pass, 100% branch coverage, and ruff and mypy are clean.

- [ ] **Step 6: Commit, push, PR, verify, merge**

```bash
git add packages/steadyhand/src/steadyhand/_validate.py packages/steadyhand/src/steadyhand/types.py tests/engine/test_validate.py tests/engine/test_types.py
git commit -m "feat(engine): self-validating trading value types (S4)"
```
Ask Shyden to run `git push -u origin m1/s4-types`, and confirm with `git ls-remote`. Open the PR with `Refs #<S4 issue>` and follow **Merging a story**.

---

### Task 5: S5 Portfolio

**Acceptance criteria (story text):**
1. `Portfolio` is immutable: `deposit` and `apply_fill` return a new portfolio and leave the original unchanged.
2. Cash is a ledger of signed `CashMovement`s. `cash_balance()` is their sum. `settled_cash(on)` counts only movements that have settled by `on`, and `unsettled_cash(on)` is the rest.
3. A buy debits gross plus costs on its trade date and needs that much settled cash, or it raises `InsufficientCashError`. Exactly enough is accepted. A sell credits gross minus costs on the `settles_on` date it is given.
4. Sale proceeds cannot fund a buy until they settle.
5. Selling more than is held raises `InsufficientSharesError`. A sell whose costs exceed its gross raises `NegativeProceedsError`. A full sale removes the position. A partial sale releases cost basis in proportion, rounded up.
6. An operation dated before the last movement raises `ChronologyError`. A settlement date before the trade date is refused. A fill or deposit in another currency raises `CurrencyMismatchError`.
7. `holdings_value(closes)` values positions at the given closes, and raises `MissingPriceError` naming the symbol when one is missing.
8. Constructing a `Portfolio` directly (as M5 will from the state DB) validates currency, position order and uniqueness, and ledger chronology.
9. Property tests: settled cash is never negative; the cash balance always equals an independently kept sum; settled plus unsettled equals the balance; the holdings equal the shares bought minus the shares sold; a round trip at an unchanged price loses exactly the modelled costs.
10. 100% branch coverage.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/portfolio.py`
- Test: `tests/engine/test_portfolio.py`, `tests/engine/test_portfolio_properties.py`

**Interfaces:**
- Consumes: `Money`, `Currency`, `IDR`, `CurrencyMismatchError` (Task 3); `Fill`, `Instrument`, `Position`, `Side`, `Order`, `Costs` (Task 4); `require_date` (Task 4).
- Produces (`steadyhand.portfolio`):
  - `class MovementKind(Enum)`: `DEPOSIT`, `BUY`, `SELL`.
  - `@dataclass(frozen=True, slots=True) class CashMovement: day: date; kind: MovementKind; amount: Money; settles_on: date`.
  - Errors: `InsufficientCashError(day, needed, available)`, `InsufficientSharesError(day, instrument, wanted, held)`, `NegativeProceedsError(fill)` and `ChronologyError(day, last)`, all `ValueError`; `MissingPriceError(LookupError)`.
  - `@dataclass(frozen=True, slots=True) class Portfolio: currency: Currency; positions: tuple[Position, ...] = (); ledger: tuple[CashMovement, ...] = ()`, with `empty(currency)`, `last_day -> date | None`, `cash_balance() -> Money`, `settled_cash(on: date) -> Money`, `unsettled_cash(on: date) -> Money`, `position(instrument) -> Position | None`, `holdings_value(closes: Mapping[Instrument, Money]) -> Money`, `deposit(amount: Money, on: date) -> Portfolio` and `apply_fill(fill: Fill, settles_on: date) -> Portfolio`.

- [ ] **Step 1: Branch and write the stub**

Run: `git switch develop && git pull && git switch -c m1/s5-portfolio`

File: `packages/steadyhand/src/steadyhand/portfolio.py` (stub)

```python
"""A cash-only portfolio. TDD stub: every behaviour raises until implemented."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from steadyhand.money import Currency, Money
from steadyhand.types import Fill, Instrument, Position


class MovementKind(Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class CashMovement:
    day: date
    kind: MovementKind
    amount: Money
    settles_on: date

    def __post_init__(self) -> None:
        raise NotImplementedError("CashMovement.__post_init__")


class InsufficientCashError(ValueError):
    def __init__(self, day: date, needed: Money, available: Money) -> None:
        raise NotImplementedError("InsufficientCashError.__init__")


class InsufficientSharesError(ValueError):
    def __init__(self, day: date, instrument: Instrument, wanted: int, held: int) -> None:
        raise NotImplementedError("InsufficientSharesError.__init__")


class NegativeProceedsError(ValueError):
    def __init__(self, fill: Fill) -> None:
        raise NotImplementedError("NegativeProceedsError.__init__")


class ChronologyError(ValueError):
    def __init__(self, day: date, last: date) -> None:
        raise NotImplementedError("ChronologyError.__init__")


class MissingPriceError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class Portfolio:
    currency: Currency
    positions: tuple[Position, ...] = ()
    ledger: tuple[CashMovement, ...] = ()

    def __post_init__(self) -> None:
        raise NotImplementedError("Portfolio.__post_init__")

    @classmethod
    def empty(cls, currency: Currency) -> Portfolio:
        raise NotImplementedError("Portfolio.empty")

    @property
    def last_day(self) -> date | None:
        raise NotImplementedError("Portfolio.last_day")

    def cash_balance(self) -> Money:
        raise NotImplementedError("Portfolio.cash_balance")

    def settled_cash(self, on: date) -> Money:
        raise NotImplementedError("Portfolio.settled_cash")

    def unsettled_cash(self, on: date) -> Money:
        raise NotImplementedError("Portfolio.unsettled_cash")

    def position(self, instrument: Instrument) -> Position | None:
        raise NotImplementedError("Portfolio.position")

    def holdings_value(self, closes: Mapping[Instrument, Money]) -> Money:
        raise NotImplementedError("Portfolio.holdings_value")

    def deposit(self, amount: Money, on: date) -> Portfolio:
        raise NotImplementedError("Portfolio.deposit")

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
        raise NotImplementedError("Portfolio.apply_fill")
```

- [ ] **Step 2: Write the failing unit tests**

File: `tests/engine/test_portfolio.py`

```python
"""Portfolio: an immutable cash ledger plus positions, with T+2 on sale proceeds."""

from datetime import UTC, date, datetime, timedelta

import pytest

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import Costs, Fill, Instrument, Order, Position, Side

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def day(offset: int) -> date:
    return D0 + timedelta(days=offset)


def fill(
    side: Side, quantity: int, price: int, on: date, *, fee: int = 0, stock: Instrument = BBRI
) -> Fill:
    order = Order(stock, side, quantity, on)
    return Fill(order, on, quantity, rp(price), Costs(rp(fee), rp(0), rp(0)))


def funded(amount: int = 10_000_000) -> Portfolio:
    return Portfolio.empty(IDR).deposit(rp(amount), D0)


class TestEmpty:
    def test_has_nothing(self) -> None:
        empty = Portfolio.empty(IDR)
        assert empty.cash_balance() == rp(0)
        assert empty.settled_cash(D0) == rp(0)
        assert empty.positions == ()
        assert empty.last_day is None


class TestDeposit:
    def test_is_settled_at_once(self) -> None:
        portfolio = funded()
        assert portfolio.cash_balance() == rp(10_000_000)
        assert portfolio.settled_cash(D0) == rp(10_000_000)
        assert portfolio.ledger == (CashMovement(D0, MovementKind.DEPOSIT, rp(10_000_000), D0),)

    def test_leaves_the_original_untouched(self) -> None:
        empty = Portfolio.empty(IDR)
        empty.deposit(rp(1), D0)
        assert empty.cash_balance() == rp(0)

    def test_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="a deposit must be positive, got IDR 0"):
            Portfolio.empty(IDR).deposit(rp(0), D0)

    def test_must_be_in_the_portfolio_currency(self) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio.empty(IDR).deposit(Money(1, USD), D0)

    def test_day_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="day must be a date, got datetime"):
            Portfolio.empty(IDR).deposit(rp(1), datetime(2026, 1, 5, tzinfo=UTC))


class TestBuy:
    def test_debits_gross_plus_costs_on_the_trade_date(self) -> None:
        portfolio = funded().apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))
        assert portfolio.cash_balance() == rp(10_000_000 - 1_245_000 - 450)
        assert portfolio.settled_cash(D0) == portfolio.cash_balance()
        assert portfolio.position(BBRI) == Position(BBRI, 300, rp(1_245_450))

    def test_a_second_buy_adds_to_the_position(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 100, 4_000, D0), day(2))
            .apply_fill(fill(Side.BUY, 200, 4_300, day(1), fee=10), day(3))
        )
        assert portfolio.position(BBRI) == Position(BBRI, 300, rp(400_000 + 860_010))

    def test_exactly_enough_settled_cash_is_accepted(self) -> None:
        portfolio = funded(1_245_450).apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))
        assert portfolio.cash_balance() == rp(0)

    def test_one_rupiah_short_is_refused(self) -> None:
        with pytest.raises(
            InsufficientCashError,
            match="2026-01-05: needs IDR 1,245,450 but only IDR 1,245,449 is settled",
        ):
            funded(1_245_449).apply_fill(fill(Side.BUY, 300, 4_150, D0, fee=450), day(2))

    def test_positions_stay_sorted_by_symbol(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
            .apply_fill(fill(Side.BUY, 100, 4_000, D0), day(2))
        )
        assert [p.instrument.symbol for p in portfolio.positions] == ["BBRI", "TLKM"]


class TestSell:
    def held(self) -> Portfolio:
        return funded().apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))

    def test_proceeds_are_unsettled_until_the_settlement_date(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 300, 4_000, day(1), fee=100), day(3))
        assert portfolio.unsettled_cash(day(2)) == rp(1_200_000 - 100)
        assert portfolio.settled_cash(day(2)) == rp(10_000_000 - 1_200_000)
        assert portfolio.settled_cash(day(3)) == rp(10_000_000 - 100)
        assert portfolio.unsettled_cash(day(3)) == rp(0)

    def test_sale_proceeds_cannot_fund_a_same_day_buy(self) -> None:
        cash_poor = (
            funded(1_200_000)
            .apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))
            .apply_fill(fill(Side.SELL, 300, 4_000, day(1)), day(3))
        )
        with pytest.raises(InsufficientCashError, match="needs IDR 400,000 but only IDR 0"):
            cash_poor.apply_fill(fill(Side.BUY, 100, 4_000, day(1), stock=TLKM), day(3))

    def test_a_full_sale_removes_the_position(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 300, 4_100, day(1)), day(3))
        assert portfolio.position(BBRI) is None
        assert portfolio.positions == ()

    def test_a_partial_sale_releases_cost_basis_rounded_up(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 3, 333, D0, fee=1), day(2))  # basis Rp 1,000 for 3
            .apply_fill(fill(Side.SELL, 1, 333, day(1)), day(3))
        )
        # 1/3 of Rp 1,000 is 333.33; the released basis rounds up to 334, leaving 666.
        assert portfolio.position(BBRI) == Position(BBRI, 2, rp(666))

    def test_cannot_sell_more_than_is_held(self) -> None:
        with pytest.raises(
            InsufficientSharesError, match="2026-01-06: cannot sell 301 BBRI, only 300 held"
        ):
            self.held().apply_fill(fill(Side.SELL, 301, 4_000, day(1)), day(3))

    def test_cannot_sell_what_is_not_held(self) -> None:
        with pytest.raises(InsufficientSharesError, match="cannot sell 1 TLKM, only 0 held"):
            self.held().apply_fill(fill(Side.SELL, 1, 3_000, day(1), stock=TLKM), day(3))

    def test_costs_above_the_gross_are_refused(self) -> None:
        with pytest.raises(
            NegativeProceedsError,
            match="2026-01-06: selling 1 BBRI raises IDR 4,000 but costs IDR 4,001",
        ):
            self.held().apply_fill(fill(Side.SELL, 1, 4_000, day(1), fee=4_001), day(3))

    def test_costs_equal_to_the_gross_are_allowed(self) -> None:
        portfolio = self.held().apply_fill(fill(Side.SELL, 1, 4_000, day(1), fee=4_000), day(3))
        assert portfolio.cash_balance() == rp(10_000_000 - 1_200_000)


class TestRefusals:
    def test_a_back_dated_fill_is_refused_and_changes_nothing(self) -> None:
        later = funded().deposit(rp(1), day(1))
        with pytest.raises(
            ChronologyError, match="2026-01-05 is before the last recorded movement, on 2026-01-06"
        ):
            later.apply_fill(fill(Side.BUY, 1, 100, D0), day(2))
        assert later.cash_balance() == rp(10_000_001)

    @pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
    def test_settlement_cannot_precede_the_trade(self, side: Side) -> None:
        held = funded().apply_fill(fill(Side.BUY, 100, 100, D0), D0)
        with pytest.raises(
            ValueError, match="settles on 2026-01-05, before the trade on 2026-01-06"
        ):
            held.apply_fill(fill(side, 1, 100, day(1)), D0)

    def test_settles_on_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="settles_on must be a date, got datetime"):
            funded().apply_fill(fill(Side.BUY, 1, 100, D0), datetime(2026, 1, 7, tzinfo=UTC))

    def test_a_fill_in_another_currency_is_refused(self) -> None:
        apple = Instrument("AAPL", "NASDAQ", USD)
        order = Order(apple, Side.BUY, 1, D0)
        usd_fill = Fill(order, D0, 1, Money(100, USD), Costs.zero(USD))
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            funded().apply_fill(usd_fill, day(2))

    def test_settled_cash_refuses_datetime(self) -> None:
        with pytest.raises(TypeError, match="on must be a date, got datetime"):
            funded().settled_cash(datetime(2026, 1, 5, tzinfo=UTC))


class TestValuation:
    def test_values_holdings_at_the_given_closes(self) -> None:
        portfolio = (
            funded()
            .apply_fill(fill(Side.BUY, 300, 4_000, D0), day(2))
            .apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
        )
        closes = {BBRI: rp(4_200), TLKM: rp(2_900)}
        assert portfolio.holdings_value(closes) == rp(300 * 4_200 + 100 * 2_900)

    def test_an_empty_portfolio_is_worth_nothing(self) -> None:
        assert Portfolio.empty(IDR).holdings_value({}) == rp(0)

    def test_a_missing_close_is_named(self) -> None:
        portfolio = funded().apply_fill(fill(Side.BUY, 100, 3_000, D0, stock=TLKM), day(2))
        with pytest.raises(MissingPriceError, match="no close price for TLKM"):
            portfolio.holdings_value({BBRI: rp(1)})


class TestDirectConstruction:
    def test_a_valid_snapshot_is_accepted(self) -> None:
        movement = CashMovement(D0, MovementKind.DEPOSIT, rp(5), D0)
        snapshot = Portfolio(IDR, (Position(BBRI, 1, rp(1)), Position(TLKM, 1, rp(1))), (movement,))
        assert snapshot.cash_balance() == rp(5)

    def test_positions_must_be_sorted(self) -> None:
        with pytest.raises(ValueError, match="positions must be unique and sorted"):
            Portfolio(IDR, (Position(TLKM, 1, rp(1)), Position(BBRI, 1, rp(1))))

    def test_positions_must_be_unique(self) -> None:
        with pytest.raises(ValueError, match="positions must be unique and sorted"):
            Portfolio(IDR, (Position(BBRI, 1, rp(1)), Position(BBRI, 2, rp(2))))

    def test_positions_must_be_in_the_portfolio_currency(self) -> None:
        apple = Instrument("AAPL", "NASDAQ", USD)
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio(IDR, (Position(apple, 1, Money(1, USD)),))

    def test_the_ledger_must_be_in_date_order(self) -> None:
        later = CashMovement(day(1), MovementKind.DEPOSIT, rp(1), day(1))
        earlier = CashMovement(D0, MovementKind.DEPOSIT, rp(1), D0)
        with pytest.raises(ChronologyError, match="2026-01-05 is before the last recorded"):
            Portfolio(IDR, (), (later, earlier))

    def test_movements_must_be_in_the_portfolio_currency(self) -> None:
        movement = CashMovement(D0, MovementKind.DEPOSIT, Money(1, USD), D0)
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            Portfolio(IDR, (), (movement,))

    def test_a_movement_cannot_settle_before_it_happens(self) -> None:
        with pytest.raises(
            ValueError, match="settles on 2026-01-05, before the trade on 2026-01-06"
        ):
            CashMovement(day(1), MovementKind.SELL, rp(1), D0)

    def test_movement_dates_refuse_datetime(self) -> None:
        with pytest.raises(TypeError, match="movement day must be a date"):
            CashMovement(datetime(2026, 1, 5, tzinfo=UTC), MovementKind.DEPOSIT, rp(1), D0)
```

- [ ] **Step 3: Write the failing property tests**

File: `tests/engine/test_portfolio_properties.py`

```python
"""Invariants that must hold after any sequence of deposits, buys and sells (spec §10.2)."""

from contextlib import suppress
from datetime import date, timedelta

from hypothesis import example, given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.portfolio import (
    InsufficientCashError,
    InsufficientSharesError,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import Costs, Fill, Instrument, Order, Side

D0 = date(2026, 1, 5)
STOCKS = (
    Instrument("ASII", "IDX", IDR),
    Instrument("BBRI", "IDX", IDR),
    Instrument("TLKM", "IDX", IDR),
)

type Step = tuple[str, int, int, int, int, int]  # kind, days forward, stock, shares, price, fee

STEP = st.tuples(
    st.sampled_from(["deposit", "buy", "sell"]),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=len(STOCKS) - 1),
    st.integers(min_value=1, max_value=5_000),
    st.integers(min_value=50, max_value=20_000),
    st.integers(min_value=0, max_value=50_000),
)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def make_fill(side: Side, stock: Instrument, shares: int, price: int, fee: int, on: date) -> Fill:
    return Fill(Order(stock, side, shares, on), on, shares, rp(price), Costs(rp(fee), rp(0), rp(0)))


@given(st.lists(STEP, max_size=40))
@example(
    [
        ("deposit", 0, 0, 5_000, 0, 0),
        ("buy", 0, 1, 300, 4_000, 450),
        ("sell", 1, 1, 100, 4_100, 200),
        ("buy", 2, 2, 100, 3_000, 0),
    ]
)
def test_cash_and_share_invariants(steps: list[Step]) -> None:
    portfolio = Portfolio.empty(IDR)
    today = D0
    expected_cash = 0
    expected_shares = dict.fromkeys(STOCKS, 0)
    for kind, forward, stock_index, shares, price, fee in steps:
        today += timedelta(days=forward)
        stock = STOCKS[stock_index]
        with suppress(InsufficientCashError, InsufficientSharesError, NegativeProceedsError):
            # A refused step raises before `portfolio` is rebound, so the snapshot is unchanged.
            if kind == "deposit":
                portfolio = portfolio.deposit(rp(shares * 1_000), today)
                expected_cash += shares * 1_000
            elif kind == "buy":
                buy = make_fill(Side.BUY, stock, shares, price, fee, today)
                portfolio = portfolio.apply_fill(buy, today + timedelta(days=2))
                expected_cash -= shares * price + fee
                expected_shares[stock] += shares
            else:
                sell = make_fill(Side.SELL, stock, shares, price, fee, today)
                portfolio = portfolio.apply_fill(sell, today + timedelta(days=2))
                expected_cash += shares * price - fee
                expected_shares[stock] -= shares
        assert portfolio.cash_balance() == rp(expected_cash)
        for probe in (today, today + timedelta(days=1), today + timedelta(days=2)):
            assert portfolio.settled_cash(probe).amount >= 0
        balance = portfolio.settled_cash(today) + portfolio.unsettled_cash(today)
        assert balance == portfolio.cash_balance()
        held = {s: (p.quantity if (p := portfolio.position(s)) else 0) for s in STOCKS}
        assert held == expected_shares


@given(
    shares=st.integers(min_value=1, max_value=10_000),
    price=st.integers(min_value=50, max_value=50_000),
    buy_fee=st.integers(min_value=0, max_value=100_000),
    data=st.data(),
)
def test_a_round_trip_at_an_unchanged_price_loses_exactly_the_costs(
    shares: int, price: int, buy_fee: int, data: st.DataObject
) -> None:
    sell_fee = data.draw(st.integers(min_value=0, max_value=shares * price), label="sell_fee")
    start = shares * price + buy_fee
    stock = STOCKS[1]
    buy = make_fill(Side.BUY, stock, shares, price, buy_fee, D0)
    sell = make_fill(Side.SELL, stock, shares, price, sell_fee, D0 + timedelta(days=1))
    after = (
        Portfolio.empty(IDR)
        .deposit(rp(start), D0)
        .apply_fill(buy, D0 + timedelta(days=2))
        .apply_fill(sell, D0 + timedelta(days=3))
    )
    assert after.cash_balance() == rp(start - buy_fee - sell_fee)
    assert after.settled_cash(D0 + timedelta(days=3)) == after.cash_balance()
    assert after.position(stock) is None
```

The `@example` guarantees at least one run where a deposit, a buy, a partial sell and a second buy all succeed, so the invariants are exercised on real state and not only on refused steps.

- [ ] **Step 4: Run against the stub**

Run: `uv run pytest tests/engine/test_portfolio.py tests/engine/test_portfolio_properties.py`
Expected: every test fails with `NotImplementedError` naming a `Portfolio` or `CashMovement` member, and none passes. Both files collect, because the module-level `Instrument` and `Money` constants come from Tasks 3 and 4, which are real.

- [ ] **Step 5: Implement**

File: `packages/steadyhand/src/steadyhand/portfolio.py`

```python
"""A cash-only portfolio: a ledger of cash movements plus the positions they bought.

A ``Portfolio`` is an immutable snapshot, and every operation returns a new one. That makes a
failed step harmless (the old snapshot is still there) and lets the daily run commit or discard
a whole day at once.

Each ``CashMovement`` carries the date it settles, so T+2 is a date comparison, not a separate
balance to keep in step. Buys are debited on the trade date, which is conservative: the broker
takes the money at settlement, but the cash is never available to spend twice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from steadyhand._validate import require_date
from steadyhand.money import Currency, CurrencyMismatchError, Money
from steadyhand.types import Fill, Instrument, Position, Side


class MovementKind(Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class CashMovement:
    """One change to cash. Credits are positive and debits negative."""

    day: date
    kind: MovementKind
    amount: Money
    settles_on: date

    def __post_init__(self) -> None:
        require_date(self.day, "movement day")
        require_date(self.settles_on, "settles_on")
        if self.settles_on < self.day:
            raise _settlement_before_trade(self.settles_on, self.day)


class InsufficientCashError(ValueError):
    """A buy needs more settled cash than the portfolio has."""

    def __init__(self, day: date, needed: Money, available: Money) -> None:
        super().__init__(f"{day.isoformat()}: needs {needed} but only {available} is settled")


class InsufficientSharesError(ValueError):
    """A sell asks for more shares than are held. There is no shorting."""

    def __init__(self, day: date, instrument: Instrument, wanted: int, held: int) -> None:
        super().__init__(
            f"{day.isoformat()}: cannot sell {wanted} {instrument.symbol}, only {held} held"
        )


class NegativeProceedsError(ValueError):
    """A sell would cost more than it raises."""

    def __init__(self, fill: Fill) -> None:
        super().__init__(
            f"{fill.day.isoformat()}: selling {fill.quantity} {fill.order.instrument.symbol} "
            f"raises {fill.gross} but costs {fill.costs.total}"
        )


class ChronologyError(ValueError):
    """An operation is dated before the last one already recorded."""

    def __init__(self, day: date, last: date) -> None:
        super().__init__(
            f"{day.isoformat()} is before the last recorded movement, on {last.isoformat()}"
        )


class MissingPriceError(LookupError):
    """A held instrument has no price to value it at."""


def _settlement_before_trade(settles_on: date, day: date) -> ValueError:
    return ValueError(f"settles on {settles_on.isoformat()}, before the trade on {day.isoformat()}")


def _sort_key(position: Position) -> tuple[str, str]:
    return (position.instrument.market, position.instrument.symbol)


@dataclass(frozen=True, slots=True)
class Portfolio:
    """An immutable snapshot of cash (as a ledger) and positions (sorted by market, symbol)."""

    currency: Currency
    positions: tuple[Position, ...] = ()
    ledger: tuple[CashMovement, ...] = ()

    def __post_init__(self) -> None:
        keys = [_sort_key(p) for p in self.positions]
        if keys != sorted(set(keys)):
            msg = "positions must be unique and sorted by market, then symbol"
            raise ValueError(msg)
        for position in self.positions:
            if position.instrument.currency != self.currency:
                raise CurrencyMismatchError(self.currency, position.instrument.currency)
        previous: date | None = None
        for movement in self.ledger:
            if movement.amount.currency != self.currency:
                raise CurrencyMismatchError(self.currency, movement.amount.currency)
            if previous is not None and movement.day < previous:
                raise ChronologyError(movement.day, previous)
            previous = movement.day

    @classmethod
    def empty(cls, currency: Currency) -> Portfolio:
        return cls(currency)

    @property
    def last_day(self) -> date | None:
        return self.ledger[-1].day if self.ledger else None

    def cash_balance(self) -> Money:
        return sum((m.amount for m in self.ledger), start=Money.zero(self.currency))

    def settled_cash(self, on: date) -> Money:
        require_date(on, "on")
        settled = (m.amount for m in self.ledger if m.settles_on <= on)
        return sum(settled, start=Money.zero(self.currency))

    def unsettled_cash(self, on: date) -> Money:
        return self.cash_balance() - self.settled_cash(on)

    def position(self, instrument: Instrument) -> Position | None:
        for position in self.positions:
            if position.instrument == instrument:
                return position
        return None

    def holdings_value(self, closes: Mapping[Instrument, Money]) -> Money:
        total = Money.zero(self.currency)
        for position in self.positions:
            close = closes.get(position.instrument)
            if close is None:
                msg = f"no close price for {position.instrument.symbol}"
                raise MissingPriceError(msg)
            total += close * position.quantity
        return total

    def deposit(self, amount: Money, on: date) -> Portfolio:
        self._require_not_before_last(on)
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            msg = f"a deposit must be positive, got {amount}"
            raise ValueError(msg)
        movement = CashMovement(on, MovementKind.DEPOSIT, amount, on)
        return Portfolio(self.currency, self.positions, (*self.ledger, movement))

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
        """Book a fill. A buy is debited on its trade date; a sell is credited on *settles_on*."""
        self._require_not_before_last(fill.day)
        require_date(settles_on, "settles_on")
        if settles_on < fill.day:
            raise _settlement_before_trade(settles_on, fill.day)
        if fill.price.currency != self.currency:
            raise CurrencyMismatchError(self.currency, fill.price.currency)
        if fill.order.side is Side.BUY:
            return self._buy(fill)
        return self._sell(fill, settles_on)

    def _require_not_before_last(self, day: date) -> None:
        require_date(day, "day")
        last = self.last_day
        if last is not None and day < last:
            raise ChronologyError(day, last)

    def _buy(self, fill: Fill) -> Portfolio:
        instrument = fill.order.instrument
        cost = fill.gross + fill.costs.total
        available = self.settled_cash(fill.day)
        if cost > available:
            raise InsufficientCashError(fill.day, cost, available)
        held = self.position(instrument)
        if held is None:
            updated = Position(instrument, fill.quantity, cost)
        else:
            updated = Position(instrument, held.quantity + fill.quantity, held.cost_basis + cost)
        movement = CashMovement(fill.day, MovementKind.BUY, -cost, fill.day)
        return self._with(movement, instrument, updated)

    def _sell(self, fill: Fill, settles_on: date) -> Portfolio:
        instrument = fill.order.instrument
        held = self.position(instrument)
        if held is None or fill.quantity > held.quantity:
            held_quantity = 0 if held is None else held.quantity
            raise InsufficientSharesError(fill.day, instrument, fill.quantity, held_quantity)
        proceeds = fill.gross - fill.costs.total
        if proceeds.amount < 0:
            raise NegativeProceedsError(fill)
        remaining: Position | None = None
        if fill.quantity < held.quantity:
            # The basis released by a partial sale rounds up, so the gain reported on the
            # shares sold is never overstated.
            released = -(-held.cost_basis.amount * fill.quantity // held.quantity)
            remaining = Position(
                instrument,
                held.quantity - fill.quantity,
                Money(held.cost_basis.amount - released, self.currency),
            )
        movement = CashMovement(fill.day, MovementKind.SELL, proceeds, settles_on)
        return self._with(movement, instrument, remaining)

    def _with(
        self, movement: CashMovement, instrument: Instrument, position: Position | None
    ) -> Portfolio:
        others = [p for p in self.positions if p.instrument != instrument]
        if position is not None:
            others.append(position)
        positions = tuple(sorted(others, key=_sort_key))
        return Portfolio(self.currency, positions, (*self.ledger, movement))
```

- [ ] **Step 6: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
```
Expected: all pass, 100% branch coverage including `portfolio.py`, and ruff and mypy are clean.

- [ ] **Step 7: Commit, push, PR, verify, merge**

```bash
git add packages/steadyhand/src/steadyhand/portfolio.py tests/engine/test_portfolio.py tests/engine/test_portfolio_properties.py
git commit -m "feat(engine): immutable cash-only Portfolio with T+2 proceeds (S5)"
```
Ask Shyden to run `git push -u origin m1/s5-portfolio`, and confirm with `git ls-remote`. Open the PR with `Refs #<S5 issue>` and follow **Merging a story**.

---

### Task 6: S6 Plug-in protocols

**Acceptance criteria (story text):**
1. `steadyhand.market.MarketRules`, `steadyhand.data.DataSource` and `steadyhand.broker.Broker` are `runtime_checkable` Protocols with the signatures in step 3, and each method's docstring states its contract.
2. A minimal conforming class type-checks against each protocol under `mypy --strict` and passes `isinstance`. A class missing a method fails `isinstance`.
3. `DataUnavailableError` exists for data sources to fail closed with, and its message is the caller's.
4. 100% branch coverage.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/market.py`, `packages/steadyhand/src/steadyhand/data.py`, `packages/steadyhand/src/steadyhand/broker/__init__.py`, `packages/steadyhand/src/steadyhand/broker/protocol.py`
- Test: `tests/engine/test_protocols.py`

**Interfaces:**
- Consumes: `Money`, `Currency` (Task 3); `Bar`, `CorporateAction`, `Costs`, `Fill`, `Instrument`, `Order`, `OrderAck`, `Side` (Task 4).
- Produces:
  - `MarketRules`: `currency` (read-only property), `lot_size(instrument, on) -> int`, `round_to_tick(instrument, price, side, on) -> Money`, `price_band(instrument, reference, on) -> tuple[Money, Money]`, `costs(side, gross, on) -> Costs`, `settlement_date(trade_date) -> date`, `dividend_tax(gross, *, reinvested_by_deadline, on) -> Money` and `is_trading_day(day) -> bool`.
  - `DataSource`: `bars(instrument, start, end) -> Sequence[Bar]` and `corporate_actions(instrument, start, end) -> Sequence[CorporateAction]`; `DataUnavailableError(RuntimeError)`.
  - `Broker`: `submit(orders, on) -> Sequence[OrderAck]` and `fills(on) -> Sequence[Fill]`, also exported from `steadyhand.broker`.

- [ ] **Step 1: Branch and write the stubs (empty protocols)**

Run: `git switch develop && git pull && git switch -c m1/s6-protocols`

File: `packages/steadyhand/src/steadyhand/market.py` (stub)

```python
"""MarketRules protocol. TDD stub: no members yet."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketRules(Protocol):
    pass
```

File: `packages/steadyhand/src/steadyhand/data.py` (stub)

```python
"""DataSource protocol. TDD stub: no members yet."""

from typing import Protocol, runtime_checkable


class DataUnavailableError(RuntimeError):
    pass


@runtime_checkable
class DataSource(Protocol):
    pass
```

File: `packages/steadyhand/src/steadyhand/broker/__init__.py`

```python
"""Brokers: the Broker protocol."""

from steadyhand.broker.protocol import Broker

__all__ = ["Broker"]
```

File: `packages/steadyhand/src/steadyhand/broker/protocol.py` (stub)

```python
"""Broker protocol. TDD stub: no members yet."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Broker(Protocol):
    pass
```

- [ ] **Step 2: Write the failing tests**

File: `tests/engine/test_protocols.py`

```python
"""The engine's plug-in points are structural Protocols: anything with the right methods fits.

Each ``_Minimal*`` class is the smallest conforming implementation. Assigning it to a variable
typed as the protocol makes ``mypy --strict`` check every signature; ``isinstance`` checks the
runtime view that plug-in loading will use.
"""

from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.market import MarketRules
from steadyhand.money import IDR, Currency, Money
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side


class _MinimalRules:
    @property
    def currency(self) -> Currency:
        return IDR

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        return price

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        return (reference, reference)

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        return Costs.zero(gross.currency)

    def settlement_date(self, trade_date: date) -> date:
        return trade_date + timedelta(days=2)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class _MinimalSource:
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return ()

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return ()


class _MinimalBroker:
    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]:
        return [OrderAck(order, accepted=True) for order in orders]

    def fills(self, on: date) -> Sequence[Fill]:
        return ()


class _RulesWithoutTax:
    currency = IDR

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100


def test_a_minimal_class_satisfies_market_rules() -> None:
    rules: MarketRules = _MinimalRules()
    assert isinstance(rules, MarketRules)


def test_a_class_missing_methods_is_not_market_rules() -> None:
    assert not isinstance(_RulesWithoutTax(), MarketRules)


def test_a_minimal_class_satisfies_data_source() -> None:
    source: DataSource = _MinimalSource()
    assert isinstance(source, DataSource)
    assert not isinstance(_MinimalBroker(), DataSource)


def test_a_minimal_class_satisfies_broker() -> None:
    broker: Broker = _MinimalBroker()
    assert isinstance(broker, Broker)
    assert not isinstance(_MinimalSource(), Broker)


def test_data_unavailable_keeps_the_callers_message() -> None:
    message = "BBRI.JK bars after 3 attempts"
    with pytest.raises(DataUnavailableError, match=r"^BBRI\.JK bars after 3 attempts$"):
        raise DataUnavailableError(message)
```

- [ ] **Step 3: Run against the stubs**

Run: `uv run pytest tests/engine/test_protocols.py`
Expected: 3 failed, 2 passed. The three tests with a "not an instance" assertion fail, because an empty protocol matches everything. Two pass against the stub, for the reason given: `test_a_minimal_class_satisfies_market_rules`, because anything satisfies an empty protocol (its real check is mypy's, in step 5), and `test_data_unavailable_keeps_the_callers_message`, because an exception class keeping its message is Python's behaviour, not ours. That test pins the type's existence and base class.

- [ ] **Step 4: Implement**

File: `packages/steadyhand/src/steadyhand/market.py`

```python
"""The MarketRules protocol: everything that differs between stock exchanges."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
from steadyhand.types import Costs, Instrument, Side


@runtime_checkable
class MarketRules(Protocol):
    """One market's trading rules. Every rule is looked up for a date, because rules change.

    An implementation reads its values from dated data (spec §9.1), never from constants, so a
    backtest over past dates uses the rules that applied on those dates.
    """

    @property
    def currency(self) -> Currency:
        """The currency every price and cost in this market is quoted in."""
        ...

    def lot_size(self, instrument: Instrument, on: date) -> int:
        """Shares per board lot. Orders are whole lots."""
        ...

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        """The nearest valid price against the trader: up for a BUY, down for a SELL."""
        ...

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The (lowest, highest) price the exchange accepts, given the reference price."""
        ...

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        """Fee, levy and tax for one trade of *gross* value. Never negative."""
        ...

    def settlement_date(self, trade_date: date) -> date:
        """The trading day on which a trade made on *trade_date* settles."""
        ...

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """The tax withheld from a *gross* dividend paid on *on*."""
        ...

    def is_trading_day(self, day: date) -> bool:
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...
```

File: `packages/steadyhand/src/steadyhand/data.py`

```python
"""The DataSource protocol: where prices and corporate actions come from."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Bar, CorporateAction, Instrument


class DataUnavailableError(RuntimeError):
    """A data source could not supply what was asked for. The daily run stops without trading."""


@runtime_checkable
class DataSource(Protocol):
    """A supplier of **unadjusted** daily bars and corporate actions.

    Both methods cover *start* to *end* inclusive, return items in date order, and raise
    ``DataUnavailableError`` rather than return partial data (fail closed).
    """

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        """Unadjusted OHLCV bars, one per trading day with data."""
        ...

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        """Splits, cash dividends and other actions with an ex-date in the range."""
        ...
```

File: `packages/steadyhand/src/steadyhand/broker/protocol.py`

```python
"""The Broker protocol: where orders go and fills come from."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Fill, Order, OrderAck


@runtime_checkable
class Broker(Protocol):
    """Accepts orders and reports what filled. The simulated broker arrives in M3."""

    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]:
        """Queue *orders* placed on *on*. Returns one acknowledgement per order, in order."""
        ...

    def fills(self, on: date) -> Sequence[Fill]:
        """Everything that filled on *on*."""
        ...
```

`broker/__init__.py` is final as written in step 1: it only re-exports.

- [ ] **Step 5: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
```
Expected: all pass, and coverage stays 100% because the `...` bodies are excluded by the `exclude_also` rule from Task 1.

- [ ] **Step 6: Commit, then prove that mypy checks the protocol shape**

```bash
git add packages/steadyhand/src/steadyhand/market.py packages/steadyhand/src/steadyhand/data.py packages/steadyhand/src/steadyhand/broker tests/engine/test_protocols.py
git commit -m "feat(engine): MarketRules, DataSource and Broker protocols (S6)"
```
In `tests/engine/test_protocols.py`, change `_MinimalRules.lot_size` to `-> str` with `return "100"`, then run `uv run mypy`. Expected: an `Incompatible types in assignment` error at `rules: MarketRules = _MinimalRules()` whose notes name `lot_size`. Revert with `git checkout -- tests/engine/test_protocols.py` (safe, because the commit above holds the real file).

- [ ] **Step 7: Push, PR, verify, merge**

Ask Shyden to run `git push -u origin m1/s6-protocols`, and confirm with `git ls-remote`. Open the PR with `Refs #<S6 issue>` and follow **Merging a story**.

---

### Task 7: S7 Codebase meta-guards and public API

**Acceptance criteria (story text):**
1. `tests/meta/test_no_float.py` fails if a `float` name, a float or complex literal, or a string annotation containing `float` appears in the guarded engine modules (spec §10.1). It walks the AST, so comments and ordinary strings do not count.
2. `tests/meta/test_dependencies.py` fails if the engine declares any runtime dependency, if any engine module imports anything outside the standard library and `steadyhand`, or if `steadyhand-idx` imports a private (`_`-prefixed) engine module or name.
3. `tests/meta/test_public_api.py` fails if a public class, function, type alias or ALL-CAPS constant in a public engine module is missing from `steadyhand.__all__` or is a different object there, or if `__all__` lists something that is not defined.
4. `tests/meta/test_disclaimer.py` pins `steadyhand.DISCLAIMER` to the exact text and fails if any README lacks it.
5. Every detector has a positive control in its own tests, and every guard is mutation-verified (step 7), with the results in the PR body.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/disclaimer.py`
- Modify: `packages/steadyhand/src/steadyhand/__init__.py`
- Test: `tests/meta/test_no_float.py`, `tests/meta/test_dependencies.py`, `tests/meta/test_public_api.py`, `tests/meta/test_disclaimer.py`

**Interfaces:**
- Consumes: every engine module from Tasks 1 and 3–6.
- Produces: `steadyhand.DISCLAIMER: Final[str]` (M5 prints it in `init` and in report footers; M6+ guides carry it), and the complete `steadyhand.__all__`.

- [ ] **Step 1: Branch and write the guards with stubbed detectors**

Run: `git switch develop && git pull && git switch -c m1/s7-meta-guards`

Write each test file as in step 3, but with every helper function's body replaced by `raise NotImplementedError("<helper name>")`: `float_uses` and `guarded_files` in `test_no_float.py`, `top_level_imports` and `private_engine_imports` in `test_dependencies.py`, `public_modules` and `public_definitions` in `test_public_api.py`, and `normalised` in `test_disclaimer.py`. Also create the disclaimer stub:

File: `packages/steadyhand/src/steadyhand/disclaimer.py` (stub)

```python
"""The disclaimer. TDD stub: empty."""

from typing import Final

DISCLAIMER: Final = ""
```

- [ ] **Step 2: Run against the stubs**

Run: `uv run pytest tests/meta`
Expected: every new test fails, either with `NotImplementedError` naming its helper, or (for `test_disclaimer_text_is_pinned` and `test_every_readme_carries_the_disclaimer`) on the empty stub. The one exception is `test_engine_pyproject_declares_no_runtime_dependencies`, which uses no helper and passes because the engine really has no dependencies. Mutation M4 in step 7 proves it can fail. `test_supply_chain.py` and `test_packaging.py` still pass.

- [ ] **Step 3: Implement the guards**

File: `tests/meta/test_no_float.py`

```python
"""No ``float`` in money, weight or ledger code (spec §4.4, §10.1).

The check walks the AST, so a comment or an ordinary string that mentions float is not a
finding, while ``float(...)``, a ``1.5`` literal and a ``"float"`` string annotation are.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
GUARDED = ("money.py", "portfolio.py", "sizing.py", "risk.py", "income.py", "metrics.py", "broker")


def guarded_files() -> list[Path]:
    files: list[Path] = []
    for entry in GUARDED:
        path = ENGINE / entry
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        elif path.is_file():
            files.append(path)
    return files


def _annotations(tree: ast.AST) -> Iterator[ast.expr]:
    for node in ast.walk(tree):
        if isinstance(node, ast.arg | ast.AnnAssign) and node.annotation is not None:
            yield node.annotation
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns is not None:
            yield node.returns


def float_uses(source: str) -> list[str]:
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float":
            found.append(f"line {node.lineno}: float")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float | complex):
            kind = type(node.value).__name__
            found.append(f"line {node.lineno}: {kind} literal {node.value!r}")
    for annotation in _annotations(tree):
        for node in ast.walk(annotation):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and float_uses(node.value)
            ):
                found.append(f"line {node.lineno}: float in string annotation")
    return found


@pytest.mark.parametrize(
    ("source", "finding"),
    [
        ("x: float = 0", "line 1: float"),
        ("y = 1.5", "line 1: float literal 1.5"),
        ("z = float(1)", "line 1: float"),
        ("w = 2j", "line 1: complex literal 2j"),
        ('def f() -> "float": ...', "line 1: float in string annotation"),
        ('def g(a: "list[float]") -> None: ...', "line 1: float in string annotation"),
    ],
)
def test_detector_finds_float(source: str, finding: str) -> None:
    assert finding in float_uses(source)


def test_detector_ignores_comments_and_plain_strings() -> None:
    source = '# x: float = 1.5\nlabel = "float 1.5"\ncount: int = 2\n'
    assert float_uses(source) == []


def test_guarded_engine_modules_contain_no_float() -> None:
    files = guarded_files()
    names = {path.relative_to(ENGINE).as_posix() for path in files}
    assert {"money.py", "portfolio.py", "broker/__init__.py", "broker/protocol.py"} <= names
    findings = {
        path.relative_to(ENGINE).as_posix(): uses
        for path in files
        if (uses := float_uses(path.read_text(encoding="utf-8")))
    }
    assert findings == {}
```

File: `tests/meta/test_dependencies.py`

```python
"""The engine uses the standard library only, and the IDX package uses only its public API.

Spec §4.2. The pyproject check covers what is declared; the import walk covers what is used.
"""

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
IDX = ROOT / "packages/steadyhand-idx/src/steadyhand_idx"


def top_level_imports(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            names.add(node.module.split(".")[0])
    return names


def _is_private(part: str) -> bool:
    return part.startswith("_") and not (part.startswith("__") and part.endswith("__"))


def private_engine_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "steadyhand" and any(_is_private(p) for p in parts[1:]):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            parts = node.module.split(".")
            if parts[0] != "steadyhand":
                continue
            if any(_is_private(p) for p in parts[1:]):
                found.append(node.module)
            found.extend(
                f"{node.module}.{alias.name}" for alias in node.names if _is_private(alias.name)
            )
    return found


def test_engine_pyproject_declares_no_runtime_dependencies() -> None:
    pyproject = (ROOT / "packages/steadyhand/pyproject.toml").read_text(encoding="utf-8")
    project = tomllib.loads(pyproject)["project"]
    assert project["dependencies"] == []
    assert "optional-dependencies" not in project


def test_import_detector_sees_absolute_imports_and_skips_relative_ones() -> None:
    source = "import os.path\nfrom decimal import Decimal\nfrom . import money\nimport yaml as y\n"
    assert top_level_imports(source) == {"os", "decimal", "yaml"}


def test_engine_imports_only_the_standard_library() -> None:
    files = sorted(ENGINE.rglob("*.py"))
    assert len(files) >= 8, files
    imported = {path: top_level_imports(path.read_text(encoding="utf-8")) for path in files}
    assert "decimal" in set().union(*imported.values())
    allowed = sys.stdlib_module_names | {"steadyhand"}
    foreign = {
        path.relative_to(ENGINE).as_posix(): sorted(names - allowed)
        for path, names in imported.items()
        if names - allowed
    }
    assert foreign == {}


def test_private_import_detector() -> None:
    source = (
        "from steadyhand._validate import require_date\n"
        "import steadyhand._validate\n"
        "from steadyhand import _hidden, Money, __version__\n"
        "from steadyhand_idx._x import y\n"
        "import os\n"
    )
    assert private_engine_imports(source) == [
        "steadyhand._validate",
        "steadyhand._validate",
        "steadyhand._hidden",
    ]


def test_idx_uses_only_the_engine_public_api() -> None:
    files = sorted(IDX.rglob("*.py"))
    assert files
    found = {
        path.relative_to(IDX).as_posix(): hits
        for path in files
        if (hits := private_engine_imports(path.read_text(encoding="utf-8")))
    }
    assert found == {}
```

File: `tests/meta/test_public_api.py`

```python
"""Everything public in the engine is importable from ``steadyhand`` itself.

The expected set is derived from the source, not listed, so a new public class cannot be
forgotten from ``__all__``.
"""

import ast
import importlib
import re
from pathlib import Path

import steadyhand

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages/steadyhand/src"
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")


def public_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted((SRC / "steadyhand").rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if any(part.startswith("_") for part in parts):
            continue  # private modules, and __init__ files, which only re-export
        modules.append(".".join(parts))
    return modules


def public_definitions(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.TypeAlias):
            name = node.name if not isinstance(node, ast.TypeAlias) else node.name.id
            if not name.startswith("_"):
                names.add(name)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(
                t.id for t in targets if isinstance(t, ast.Name) and CONSTANT.fullmatch(t.id)
            )
    return names


def definitions() -> dict[str, str]:
    """Every public name, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules():
        path = SRC / (module.replace(".", "/") + ".py")
        for name in public_definitions(path.read_text(encoding="utf-8")):
            found[name] = module
    return found


def test_definition_detector() -> None:
    source = (
        "class A: ...\nclass _B: ...\ndef f() -> None: ...\ntype T = int\n"
        "LIMIT = 1\nTYPED: int = 2\n_PRIVATE = 3\nlower = 4\n"
    )
    assert public_definitions(source) == {"A", "f", "T", "LIMIT", "TYPED"}


def test_every_public_definition_is_exported_as_the_same_object() -> None:
    found = definitions()
    assert {"Money", "Portfolio", "MarketRules", "Broker", "DISCLAIMER"} <= set(found)
    missing = sorted(set(found) - set(steadyhand.__all__))
    assert missing == []
    wrong = sorted(
        name
        for name, module in found.items()
        if getattr(steadyhand, name) is not getattr(importlib.import_module(module), name)
    )
    assert wrong == []


def test_all_lists_only_defined_names() -> None:
    extra = sorted(set(steadyhand.__all__) - set(definitions()) - {"__version__"})
    assert extra == []
```

File: `tests/meta/test_disclaimer.py`

```python
"""The disclaimer is written once and shown everywhere it must be (spec §9.8)."""

from pathlib import Path

from steadyhand.disclaimer import DISCLAIMER

ROOT = Path(__file__).resolve().parents[2]


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, with quote markers removed."""
    lines = (line.strip().removeprefix(">").strip() for line in markdown.splitlines())
    return " ".join(" ".join(lines).split())


def test_disclaimer_text_is_pinned() -> None:
    assert DISCLAIMER == (
        "steadyhand is example software that you run yourself, on your own account, and you "
        "make your own decisions with it. It is not financial advice. You can lose money."
    )


def test_normalising_joins_wrapped_quoted_lines() -> None:
    assert normalised("> one\n> two  three\n") == "one two three"


def test_every_readme_carries_the_disclaimer() -> None:
    assert len(DISCLAIMER.split()) >= 10  # an empty disclaimer is "in" every file
    readmes = [ROOT / "README.md", *sorted(ROOT.glob("packages/*/README.md"))]
    assert len(readmes) == 3
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in readmes
        if DISCLAIMER not in normalised(path.read_text(encoding="utf-8"))
    ]
    assert missing == []
```

- [ ] **Step 4: Run and watch the product-side guards fail**

Run: `uv run pytest tests/meta`
Expected: 3 failed. `test_disclaimer_text_is_pinned` and `test_every_readme_carries_the_disclaimer` fail on the still-empty stub, and `test_every_public_definition_is_exported…` fails, listing every engine name missing from `__all__`. Every detector test, every no-float and dependency test, and `test_all_lists_only_defined_names` pass.

- [ ] **Step 5: Implement the disclaimer and the public API**

File: `packages/steadyhand/src/steadyhand/disclaimer.py`

```python
"""The disclaimer every user-facing surface carries (spec §9.8). Written once, here."""

from typing import Final

DISCLAIMER: Final = (
    "steadyhand is example software that you run yourself, on your own account, and you "
    "make your own decisions with it. It is not financial advice. You can lose money."
)
```

File: `packages/steadyhand/src/steadyhand/__init__.py`

```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.market import MarketRules
from steadyhand.money import (
    IDR,
    MAX_MINOR_UNITS,
    Currency,
    CurrencyMismatchError,
    Money,
    Rounding,
)
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)

__version__: str = version("steadyhand")

__all__ = [
    "DISCLAIMER",
    "IDR",
    "MAX_MINOR_UNITS",
    "Bar",
    "Broker",
    "CashDividend",
    "CashMovement",
    "ChronologyError",
    "CorporateAction",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "DataSource",
    "DataUnavailableError",
    "Fill",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "MarketRules",
    "MissingPriceError",
    "Money",
    "MovementKind",
    "NegativeProceedsError",
    "Order",
    "OrderAck",
    "OtherAction",
    "Portfolio",
    "Position",
    "Rounding",
    "Side",
    "Split",
    "__version__",
]
```


- [ ] **Step 6: Run every gate and commit**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
git add packages/steadyhand/src/steadyhand/disclaimer.py packages/steadyhand/src/steadyhand/__init__.py tests/meta
git commit -m "test(meta): no-float, dependency, public-API and disclaimer guards (S7)"
```
Expected: all pass, 100% branch coverage, and ruff and mypy are clean. Commit before step 7.

- [ ] **Step 7: Mutation-verify each guard**

Same procedure as Task 2, step 7: predict, apply, print the changed line, run the **whole** `tests/meta` directory, then revert with `git checkout -- <file>`.

| # | Mutation (leave any comment naming it in place) | Predicted result |
|---|---|---|
| M1 | Add `_SCALE = 1.5  # float: remove before merge` to `money.py` | `test_guarded_engine_modules_contain_no_float` fails: `money.py: line N: float literal 1.5` |
| M2 | Change `def zero(cls, currency: Currency) -> Money:` in `money.py` to `-> "float | Money":` | the same test fails: `float in string annotation` |
| M3 | Add `# amount: float` as a comment in `portfolio.py` | every guard still passes: a comment is not a finding |
| M4 | Set `dependencies = ["requests"]` in the engine pyproject (no `uv sync`) | `test_engine_pyproject_declares_no_runtime_dependencies` fails |
| M5 | Add `import yaml` to `types.py` | `test_engine_imports_only_the_standard_library` fails: `types.py: ['yaml']` |
| M6 | Add `from steadyhand._validate import require_date` to `steadyhand_idx/__init__.py` | `test_idx_uses_only_the_engine_public_api` fails |
| M7 | Remove `"Split"` from `__all__` (leave its import) | `test_every_public_definition_is_exported…` fails: `['Split']` |
| M8 | Add `"Ghost"` to `__all__` | `test_all_lists_only_defined_names` fails: `['Ghost']`. `test_every_exported_name_resolves` fails too |
| M9 | Change "You can lose money." to "You may lose money." in `packages/steadyhand-idx/README.md` | `test_every_readme_carries_the_disclaimer` fails: `['packages/steadyhand-idx/README.md']` |

Record each result in the PR body.

- [ ] **Step 8: Push, PR, verify, merge**

Ask Shyden to run `git push -u origin m1/s7-meta-guards`, and confirm with `git ls-remote`. Open the PR with `Refs #<S7 issue>` and follow **Merging a story**.

---

### Task 8: S8 TestPyPI dev publishing

**Blocked on OP-1.** Shyden creates a *pending publisher* on TestPyPI (test.pypi.org, then Account, then Publishing) for **each** of `steadyhand` and `steadyhand-idx`, with: owner `ShydenMcM`, repository `steadyhand`, workflow `ci.yml`, environment `testpypi`. Ask for this with `AskUserQuestion` when M1 reaches this task, and do not merge until it is confirmed.

**Acceptance criteria (story text):**
1. A push to `develop` that passes `lint`, `test`, `audit` and `build` runs `publish-dev`. It rewrites both versions to `0.1.0.dev<run_number>`, pins `steadyhand-idx` to exactly that engine version, builds, and publishes both packages to TestPyPI through trusted publishing (OIDC, no stored token).
2. `publish-dev` then installs both packages from TestPyPI into a fresh virtualenv (retrying for up to 5 minutes while the index catches up) and checks that both `__version__` values equal the published version.
3. The job runs only on push to `develop`, in the `testpypi` environment, whose deployment branch policy allows only `develop`. It is the only job with `id-token: write`.
4. `scripts/set_dev_version.py` refuses (exit 2, message on stderr) bad usage, and raises `VersionError` for any pyproject that is not in the shape it rewrites. It is tested.
5. After the first merge, the run is read job by job. `publish-dev` and its verify step are `success`, and both packages are visible on test.pypi.org at the run's version.

**Files:**
- Create: `scripts/set_dev_version.py`
- Modify: `.github/workflows/ci.yml` (add the `publish-dev` job), `pyproject.toml` (mypy `files`, pytest `pythonpath`)
- Test: `tests/scripts/test_set_dev_version.py`

**Interfaces:**
- Consumes: the package pyprojects and the CI jobs from Task 1.
- Produces: `set_dev_version(run_number: int, engine: Path | None = None, idx: Path | None = None) -> str`, `main(argv: list[str]) -> int` and `VersionError(RuntimeError)`.

- [ ] **Step 1: Branch, extend mypy, and create the GitHub environment**

```bash
git switch develop && git pull && git switch -c m1/s8-dev-publish
gh api -X PUT repos/ShydenMcM/steadyhand/environments/testpypi --input - <<'EOF'
{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
gh api -X POST repos/ShydenMcM/steadyhand/environments/testpypi/deployment-branch-policies -f name=develop -f type=branch
gh api repos/ShydenMcM/steadyhand/environments/testpypi/deployment-branch-policies --jq '[.branch_policies[].name]'
```
Expected: `["develop"]`. In `pyproject.toml`, change `files = ["packages", "tests"]` to `files = ["packages", "tests", "scripts"]`, and add `pythonpath = ["scripts"]` under `[tool.pytest.ini_options]`.

- [ ] **Step 2: Write the stub and the failing tests**

File: `scripts/set_dev_version.py` (stub)

```python
"""Set a development version on both packages. TDD stub."""

from pathlib import Path


class VersionError(RuntimeError):
    pass


def set_dev_version(run_number: int, engine: Path | None = None, idx: Path | None = None) -> str:
    raise NotImplementedError("set_dev_version")


def main(argv: list[str]) -> int:
    raise NotImplementedError("main")
```

File: `tests/scripts/test_set_dev_version.py`

```python
"""The dev-version script rewrites exactly what it should, and refuses anything else."""

import shutil
import tomllib
from pathlib import Path

import pytest

import set_dev_version
from set_dev_version import VersionError, main

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def copies(tmp_path: Path) -> tuple[Path, Path]:
    engine = tmp_path / "engine.toml"
    idx = tmp_path / "idx.toml"
    shutil.copyfile(ROOT / "packages/steadyhand/pyproject.toml", engine)
    shutil.copyfile(ROOT / "packages/steadyhand-idx/pyproject.toml", idx)
    return engine, idx


def project(path: Path) -> dict[str, object]:
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    assert isinstance(loaded, dict)
    return loaded


def test_rewrites_both_versions_and_pins_the_engine(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    assert set_dev_version.set_dev_version(7, engine, idx) == "0.1.0.dev7"
    assert project(engine)["version"] == "0.1.0.dev7"
    assert project(idx)["version"] == "0.1.0.dev7"
    assert project(idx)["dependencies"] == ["steadyhand==0.1.0.dev7"]


def test_refuses_a_run_number_below_one(copies: tuple[Path, Path]) -> None:
    with pytest.raises(VersionError, match="run number must be positive, got 0"):
        set_dev_version.set_dev_version(0, *copies)


def test_refuses_mismatched_versions(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    idx.write_text(
        idx.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.2.0"')
    )
    with pytest.raises(
        VersionError, match=r"steadyhand-idx is at 0\.2\.0 but the engine is at 0\.1\.0"
    ):
        set_dev_version.set_dev_version(1, engine, idx)


def test_refuses_an_engine_without_a_plain_version(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    engine.write_text(
        engine.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.1"')
    )
    with pytest.raises(VersionError, match=r"engine\.toml: expected exactly one match"):
        set_dev_version.set_dev_version(1, engine, idx)


def test_refuses_an_idx_without_the_engine_dependency_line(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    idx.write_text(
        idx.read_text(encoding="utf-8").replace('    "steadyhand",\n', '    "steadyhand>=0.1",\n')
    )
    with pytest.raises(VersionError, match=r"idx\.toml: expected exactly one match"):
        set_dev_version.set_dev_version(1, engine, idx)
    assert project(engine)["version"] == "0.1.0"  # nothing is written unless both rewrite


@pytest.mark.parametrize("argv", [["set_dev_version.py"], ["set_dev_version.py", "x"]])
def test_main_refuses_bad_usage(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 2
    assert "usage: set_dev_version.py <run-number>" in capsys.readouterr().err


def test_main_prints_the_version(
    copies: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(set_dev_version, "ENGINE", copies[0])
    monkeypatch.setattr(set_dev_version, "IDX", copies[1])
    assert main(["set_dev_version.py", "42"]) == 0
    assert capsys.readouterr().out == "0.1.0.dev42\n"
```

Run: `uv run pytest tests/scripts`
Expected: the file collects, and all 8 tests fail. `test_main_prints_the_version` fails with `AttributeError: <module 'set_dev_version' ...> has no attribute 'ENGINE'`, because the stub defines no paths, and every other test fails with `NotImplementedError`.

- [ ] **Step 3: Implement the script**

File: `scripts/set_dev_version.py`

```python
"""Give both packages a unique development version before a TestPyPI upload.

Usage: python scripts/set_dev_version.py <run-number>

``0.1.0`` becomes ``0.1.0.dev<run-number>`` in both pyproject files, and steadyhand-idx is
pinned to exactly that engine version, so a dev install never mixes two builds. Nothing is
written unless every rewrite applies.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "packages/steadyhand/pyproject.toml"
IDX = ROOT / "packages/steadyhand-idx/pyproject.toml"
VERSION_LINE = re.compile(r'^version = "(?P<base>\d+\.\d+\.\d+)"$', re.MULTILINE)
ENGINE_DEPENDENCY = re.compile(r'^    "steadyhand",$', re.MULTILINE)
USAGE = "usage: set_dev_version.py <run-number>"


class VersionError(RuntimeError):
    """A pyproject file is not in the shape this script rewrites."""


def _replace_once(pattern: re.Pattern[str], text: str, replacement: str, path: Path) -> str:
    rewritten, count = pattern.subn(replacement, text)
    if count != 1:
        msg = f"{path.name}: expected exactly one match for {pattern.pattern!r}, found {count}"
        raise VersionError(msg)
    return rewritten


def _base_version(text: str, path: Path) -> str:
    matches = VERSION_LINE.findall(text)
    if len(matches) != 1:
        msg = (
            f"{path.name}: expected exactly one match for {VERSION_LINE.pattern!r}, "
            f"found {len(matches)}"
        )
        raise VersionError(msg)
    return str(matches[0])


def set_dev_version(run_number: int, engine: Path | None = None, idx: Path | None = None) -> str:
    engine = engine or ENGINE
    idx = idx or IDX
    if run_number < 1:
        msg = f"run number must be positive, got {run_number}"
        raise VersionError(msg)
    engine_text = engine.read_text(encoding="utf-8")
    idx_text = idx.read_text(encoding="utf-8")
    base = _base_version(engine_text, engine)
    idx_base = _base_version(idx_text, idx)
    if idx_base != base:
        msg = f"steadyhand-idx is at {idx_base} but the engine is at {base}"
        raise VersionError(msg)
    version = f"{base}.dev{run_number}"
    new_engine = _replace_once(VERSION_LINE, engine_text, f'version = "{version}"', engine)
    new_idx = _replace_once(VERSION_LINE, idx_text, f'version = "{version}"', idx)
    new_idx = _replace_once(ENGINE_DEPENDENCY, new_idx, f'    "steadyhand=={version}",', idx)
    for text in (new_engine, new_idx):
        tomllib.loads(text)  # never write a file that no longer parses
    engine.write_text(new_engine, encoding="utf-8")
    idx.write_text(new_idx, encoding="utf-8")
    return version


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].isdigit():  # noqa: PLR2004 - program name plus one argument
        print(USAGE, file=sys.stderr)
        return 2
    print(set_dev_version(int(argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Add the publish job**

Append this job to `.github/workflows/ci.yml` under `jobs:`. It is the only job with `id-token: write`, and its implicit `success()` requires every upstream job to have succeeded:

```yaml
  publish-dev:
    name: publish-dev
    if: github.event_name == 'push' && github.ref == 'refs/heads/develop'
    needs: [lint, test, audit, build]
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    environment:
      name: testpypi
      url: https://test.pypi.org/project/steadyhand/
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
      - name: Set the development version
        id: version
        env:
          RUN_NUMBER: ${{ github.run_number }}
        run: |
          version="$(uv run --no-project python scripts/set_dev_version.py "${RUN_NUMBER}")"
          echo "version=${version}" >> "${GITHUB_OUTPUT}"
      - run: uv build --all-packages --out-dir dist
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
        with:
          repository-url: https://test.pypi.org/legacy/
          packages-dir: dist/
      - name: Verify both packages install from TestPyPI
        env:
          VERSION: ${{ steps.version.outputs.version }}
        run: |
          for attempt in 1 2 3 4 5 6 7 8 9 10; do
            rm -rf "${RUNNER_TEMP}/verify"
            uv venv "${RUNNER_TEMP}/verify"
            if uv pip install --refresh --python "${RUNNER_TEMP}/verify" \
                --default-index https://test.pypi.org/simple/ \
                "steadyhand==${VERSION}" "steadyhand-idx==${VERSION}"; then
              "${RUNNER_TEMP}/verify/bin/python" -c 'import sys, steadyhand, steadyhand_idx; assert steadyhand.__version__ == steadyhand_idx.__version__ == sys.argv[1], (steadyhand.__version__, steadyhand_idx.__version__)' "${VERSION}"
              exit 0
            fi
            echo "attempt ${attempt}: not installable yet"
            sleep 30
          done
          echo "steadyhand ${VERSION} never became installable from TestPyPI" >&2
          exit 1
```

- [ ] **Step 5: Run every gate**

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check && uv run ruff format --check && uv run mypy
```
Expected: all pass, and `test_supply_chain.py` now counts the three `uses` of `publish-dev` as pinned and commented.

- [ ] **Step 6: Commit, confirm OP-1, push, PR, merge, read the deploy**

```bash
git add scripts/set_dev_version.py tests/scripts/test_set_dev_version.py .github/workflows/ci.yml pyproject.toml
git commit -m "ci: publish develop to TestPyPI as X.Y.Z.devN and verify the install (S8)"
```
Confirm OP-1 with Shyden (`AskUserQuestion`), ask for the push, open the PR with `Refs #<S8 issue>`, and follow **Merging a story**. After the merge, find the push run by SHA: `gh run list --branch develop --json databaseId,headSha,status --limit 5`, and match `headSha` to `git rev-parse origin/develop` yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`. Then read every job by name. Expected: all six are `success`, including the `Verify both packages install from TestPyPI` step. Open `https://test.pypi.org/project/steadyhand/` and `https://test.pypi.org/project/steadyhand-idx/` and check that the run's version is listed.

From this task on, every merge into `develop` is a deploy, and it is verified the same way.

---

## Carried forward to later plans

- **M3:** `Portfolio` gains entitlements, splits and dividend credits (`MovementKind.DIVIDEND` with a reinvestment-deadline tag). Measure the cost of the immutable ledger in the §10.4 performance test (10 years × 45 stocks). If `settled_cash`'s linear scan is too slow, keep running totals inside `Portfolio`. Its behaviour is fixed by this milestone's tests.
- **M3:** "portfolio value" for sizing and the daily loss limit is all cash (settled and unsettled) plus holdings at the last close, as corrected in spec §6.2 by this plan's review pass. Only settled cash can be spent.
- **M2:** when `uv add --package steadyhand-idx yfinance==<version>` rewrites `dependencies`, check that `scripts/set_dev_version.py` still finds the `    "steadyhand",` line. Its test copies the real pyproject, so the test goes red if it does not.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-24):** mechanical. Every final file block was extracted into a scratch tree and run under uv 0.12.18: pytest (216 tests, 100% branch coverage) on Python 3.12 and 3.13, `ruff check`, `ruff format --check`, `mypy --strict`, `uv build --all-packages`, a standalone engine-wheel install, and `pip-audit --strict`. Each task's stubs were overlaid to check its red-phase prediction, and every mutation in the two mutation tables, plus Task 6's mypy mutation, was applied and run. Findings, all fixed, and the verified files synced back into this plan: (1) Task 3 built `Money` in `parametrize` at collection time, which errors the whole file against the stub; (2) Task 3 step 3 had unworkable instructions for working around that; (3) `Currency` and `Instrument` raised `ValueError` for a non-string, now `TypeError`, with a new market test; (4) the property test used `try`/`except`/`pass` (bandit S110), now `contextlib.suppress`; (5) ruff: the tests needed `FBT003`/`ARG002`/`PLR0913`/`PLR0917` ignores, `known-first-party` for import grouping, and fixes for 5 long lines, 4 unescaped `match=` patterns and 1 `EM101`; (6) mypy: a narrowing lost through a local variable in `test_no_float.py`; (7) `DataUnavailableError` had a pass-through `__init__` (dead code), removed, and its red prediction corrected to 3 failed, 2 passed; (8) Task 6's mutation ran before its commit; (9) Task 7's disclaimer test imported from the package root, which errors at red; the predictions were rewritten and verified; (10) the stories table had a phantom Task 8 and a Task 9, renumbered; (11) Task 8's stub prediction was garbled; (12) `broker/__init__.py` was labelled a stub though final; (13) mutation T2-M6 also reddens a second test, now predicted; (14) the formatter reflowed 9 files, now synced.
- **Pass 2 (2026-09-24):** full read of the prose (every line outside code blocks), plus spec pass 4/5 cross-checks. Findings, all fixed: (1) **Merging a story** relied on `statusCheckRollup` to prove the checks ran on the head SHA, but it carries no SHA per check; the step now matches the run's `headSha` against the PR head, written to a file; (2) Task 6 step 5's title still promised the mypy check that moved to step 6; (3) Task 8's file list omitted the `pythonpath` change; (4) Task 4's AC did not state the new `TypeError` for non-string symbols and markets; (5) Task 7 carried a stale note about `RUF022` reordering `__all__`, but the list passes as written; (6) Task 1 step 4 did not say `uv add` appends `[dependency-groups]` to `pyproject.toml`; (7) spec §5, §6.2, §9.8 and §13 contradicted this plan and were fixed in the spec (its pass 4), then re-checked (its pass 5, 0 findings); (8) the spec's status line still said draft.
- **Pass 3 (2026-09-24):** mechanical: round-trip of every final file block against the verified tree (identical), placeholder scan (0), every interface name defined exactly once in the verified tree (16 of 16), and each `<Sn issue>` marker now has a step that fills it (Task 0 step 6, added in this pass). Full read of the prose. 1 finding, fixed: Task 0 said to wait for the push before any step, but its board and story steps do not need it.
- **Pass 4 (2026-09-24):** mechanical: round-trip against the verified tree (0 differences, 37 files), placeholder scan (0), and each of the eight `<Sn issue>` markers appears exactly once and is filled by Task 0 step 6. Read: every prose line changed since pass 2's full read, plus all of Task 0 and **Merging a story** in full; the rest is unchanged since that read. **0 findings. Loop closed. Plan approved 2026-09-24** (self-approval, per the operator's standing rule of 2026-09-24).
