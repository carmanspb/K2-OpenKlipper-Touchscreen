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
  precompiled package when changing build or runtime inputs, or use the automatic
  post-merge refresh described below.
- Describe simulator/automated checks separately from live printer testing.
  Do not run new motion, heater, cutter or CFS behavior unattended.
- Do not include credentials, personal printer configuration, identifying logs
  or proprietary firmware binaries.

## Automatic packages after merging

`Build merged touchscreen package` runs on `main` after source, test, build or
workflow changes land, and can also be started with **Run workflow**. It builds
the host simulator, runs the regression and Cartographer suites, checks C
formatting, cross-compiles the ARM executable and validates the installer bundle.
The installer context is pinned to a reviewed K2-OpenKlipper commit in the
workflow; update that pin when changing the core installer/version context.

Every successful run uploads `touchscreen-armv7-<source commit>` as a downloadable
artifact. The tarball preserves the executable permission required by the
installer. A separate write job opens or updates a single
`automation/arm-package` PR containing only `precompiled/armv7/`. Merge that PR to
update the bundle shipped from this repository. Package-only merges do not
trigger another build. Newer main builds replace older pending package updates.
This keeps all changes to main behind the repository's PR review rule.

Enable **Settings → Actions → General → Workflow permissions → Allow GitHub
Actions to create and approve pull requests** for the automatic package PR.
The workflow never approves or merges its own PR. It records the
`touchscreen/package` status on the generated commit because commits made with
`GITHUB_TOKEN` do not trigger a second PR workflow. Any other required checks
still apply; a GitHub App token would be needed to trigger those automatically.

Source PRs may omit a manual bundle rebuild when this automation will refresh it
after merging. Between the source merge and the package-refresh PR merge, the
tracked bundle may be stale and installer validation will reject it. Use the
validated workflow artifact during that interval, or merge the refresh PR before
installing directly from main. If several source PRs land in sequence, use the
refresh PR from the latest successful main build so the package includes all of
them. The workflow does not write to a source PR or resolve source conflicts.
