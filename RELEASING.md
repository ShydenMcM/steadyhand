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

   The two lines must be identical, apart from `release-cut`, which `main` alone requires once
   #400 lands (it is never posted on pull requests into `develop`). If they differ otherwise, stop: only Shyden changes `main`'s
   protection (Settings → Branches → the `main` rule → "Require status checks to pass"). Read
   both lists back after he does.
