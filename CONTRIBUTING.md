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
  precompiled package when changing build or runtime inputs.
- Describe simulator/automated checks separately from live printer testing.
  Do not run new motion, heater, cutter or CFS behavior unattended.
- Do not include credentials, personal printer configuration, identifying logs
  or proprietary firmware binaries.
