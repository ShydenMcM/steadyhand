# Release checklist

Steps taken by hand before each release is cut from `develop` into `main`. The release story
(#245) adds the build and upload steps.

## Before cutting a release

1. **`main` requires the same checks as `develop`** (#308; Shyden chose a checklist step over a
   scheduled job on 2026-11-08). Read both lists and compare them:

   ```sh
   for b in develop main; do
     gh api repos/ShydenMcM/steadyhand/branches/$b/protection/required_status_checks \
       --jq '.contexts | sort | join(",")'
   done
   ```

   The two lines must be identical, apart from `release-cut`, which `main` alone requires (it is
   never posted on pull requests into `develop`). If they differ otherwise, stop: only Shyden
   changes `main`'s protection (Settings → Branches → the `main` rule → "Require status checks to
   pass"). Read both lists back after he does.

## How a release reaches `main` (#400)

`develop` takes every ticket by squash merge; `main` takes only a frozen `release/*` branch cut
from `develop`, by merge commit. That merge commit lands on `main` and never on `develop`, so from
the second release on every cut lacks it. A strict `main` ("require branches to be up to date")
would then refuse every cut, so `main` is not strict and requires the `release-cut` status
instead; `develop` stays strict and never requires `release-cut`.

`.github/workflows/release-cut.yml` runs `scripts/release_cut.py` on every pull request into
`main`, from `develop`'s own copy of the workflow (`pull_request_target`), never the pull
request's. It posts `success`, `failure` naming the first reason, or `error` when git cannot
answer, and passes only when:

- **(a)** the head branch is `release/<something>` and origin holds it at the head;
- **(b)** the head is on `origin/develop`, where CI tested it;
- **(c)** GitHub's merge of the head into `main` lands exactly the head's tree;
- **(d)** every commit `main` holds beyond `develop` is a release merge whose second parent is on
  `develop`.

A pull request from a fork posts nothing at all: a status belongs to a SHA, which a fork can
share with a real release. The design is shyden-labs/repo-template#86 (its `docs/release-cut.md`).

### Shyden's settings, once the workflow is on `develop`

1. Settings → Branches → edit the `main` rule → untick "Require branches to be up to date before
   merging".
2. In the same rule, under "Require status checks to pass", add `release-cut` and choose
   **GitHub Actions** as its source, so only this workflow's status counts.
3. Read both back:

   ```sh
   gh api repos/ShydenMcM/steadyhand/branches/main/protection/required_status_checks \
     --jq '{strict, checks: [.checks[] | "\(.context) \(.app_id)"]}'
   ```

   `strict` is `false`, and `release-cut` is listed with app id 15368 (GitHub Actions).
   `develop` stays `strict: true`, without `release-cut`.
