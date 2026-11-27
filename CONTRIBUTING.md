# Contributing

Contributions are welcome through pull requests. Please discuss substantial
changes in an issue before implementing them.

## Pull requests

- Create a branch or fork and open a pull request targeting `main`.
- Every change to `main`, including maintainer changes, must go through a PR.
  Direct pushes, force pushes and deletion of `main` are blocked.
- @carmanspb owns all files and reviews and approves external contributions.
  Code-owner approval is required, and review conversations must be resolved.
- GitHub does not allow authors to approve their own PRs. Only @carmanspb has a
  PR-only bypass to merge maintainer-authored changes; it does not allow direct
  pushes to `main`.
- Keep the description concise: explain the problem, resulting behavior and
  validation. Include screenshots for visible UI changes.

## Development and validation

Read the [developer guide](developer-tools/README.md) for the architecture,
build instructions, simulator and tests. The current build and packaging tools
assume this component is integrated into K2 OpenKlipper's `touchscreen/` folder.

- Keep printer models, temperature limits and travel limits configuration-driven.
- Preserve homing, temperature and operation safety checks.
- Add regression tests for state handling and backend behavior changes.
- Run the relevant tests, formatting checks and package validation. Refresh the
  precompiled package when changing build or runtime inputs, or let the PR
  preparation workflow refresh it before merging.
- Describe simulator/automated checks separately from live printer testing.
  Do not run new motion, heater, cutter or CFS behavior unattended.
- Do not include credentials, personal printer configuration, identifying logs
  or proprietary firmware binaries.

## Package validation before merging

`Request PR package validation` dispatches validation when a PR changes or main
advances. Title and description edits do not dispatch package validation; base-
branch edits still do. Its `pull_request_target` job handles GitHub metadata only; it never
checks out PR code. The dispatched workflow is always loaded from main.

`Prepare and validate PR package` merges the current main into the PR branch,
resolves only generated-package conflicts, runs formatting and both test suites,
and rebuilds the package when its source fingerprints are stale. Packaging strips
PNG build timestamps without re-encoding pixels, so unchanged images remain
byte-identical across PRs. Source conflicts
stop the run for manual resolution. Successful preparation commits the main sync
and package update to the same PR branch. It never opens a binary-only PR,
approves a PR, merges a PR or pushes directly to main.

The build job runs on `ubuntu-24.04` with four parallel compile jobs and a
15-minute timeout. Small metadata, publishing and status jobs use `ubuntu-slim`
with five-minute timeouts. Slim lacks the required native build toolchain and
has a hard 15-minute job limit. ImageMagick 6 requires `librsvg2-bin` for SVG
rasterization on Ubuntu 24.04. Caches are isolated by PR and the tested source
inputs; fork builds cannot populate them. Cached builds/assets speed up repeated
validation of the same source. The installer context is pinned in the workflow.

Only the build job executes PR code, with a read-only token. The separate write
job uses helper/validator code from the trusted workflow checkout to reproduce the
exact tested merge and install validated package data. It rejects unexpected
artifact files and stale branch/main snapshots. There are no App keys or PATs;
updates use `GITHUB_TOKEN` with job-specific permissions.

A token-generated commit does not trigger ordinary PR workflows, so the updater
explicitly dispatches a fresh run. Only a successful run that makes no further
branch/package changes reports `touchscreen/package` success on that exact head.
Dispatched workflow job checks are not themselves used as the merge gate: the
workflow publishes an explicit commit status. Main advancing triggers another
preparation pass; required branch freshness prevents merging the old result.
Runs for the same PR are serialized so a follow-up cannot cancel its publishing
parent. Stale-head/main checks still prevent outdated runs from pushing or
reporting success. Cancelled attempts leave the status to their replacement run
and do not report a source/package failure.

Configure the main ruleset to require `touchscreen/package` and require branches
to be up to date. Keep the existing review and PR-only rules. Merge this workflow
PR first to activate dispatch from main; use **Run workflow** to retry or prepare
a particular PR. Forks receive read-only validation and an artifact; their author
must commit any necessary main sync or package updates before the gate passes.
No setting allowing Actions to create or approve pull requests is needed.
