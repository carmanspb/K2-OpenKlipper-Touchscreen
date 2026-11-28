# K2 Unlocked contribution and issue routing

## Scope

Native touchscreen interface, assets and component packaging.

Read this repository's CONTRIBUTING.md when present and applicable build or topic guides before editing. Preserve upstream guidance, licenses and attribution. K2 Unlocked maintenance PRs target `main`; upstream contributions follow upstream instructions.

## Find the owning component

Fix bugs in the repository that owns the behavior, including when another interface merely displays the error. Use the [repository map](https://github.com/carmanspb/k2-unlocked/blob/main/docs/development/repository-layout.md) and [issue policy](https://github.com/carmanspb/k2-unlocked/blob/main/docs/development/bug-reports.md). Distribution assembly, compatibility pins, approved OTA and cross-component release coordination belong in `k2-unlocked`.

Search for duplicates. Reports need affected versions, hardware, reproducible steps, expected and actual results, and sanitized evidence. If ownership is unclear, use the distribution tracker for triage. Route issues only to the owner's K2 Unlocked forks, never to the original upstream Klipper, Mainsail, Fluidd or other projects. Creating or transferring an upstream report requires explicit owner instruction, even if the bug reproduces upstream.

The owner authorizes agents using their access to transfer clearly misfiled issues between their repositories through GitHub's Transfer issue action or API. Preserve the original author and conversation; do not close and recreate the report. For issues created by anyone other than the owner or an agent, never change the title or description, including headings. Transfer those reports as-is; put clarifications, corrections and ownership explanations in comments. Transfer authorization does not authorize rewriting another person's report. Confirm ownership, permissions, visibility and reporter access first. GitHub blocks private-to-public transfers. Never broaden disclosure, change repository visibility, or create a public replacement without authorization. After transfer, check labels, milestones and assignees, and explain the routing in the issue. Keep one canonical bug and link necessary component or distribution tasks.

## Changes and validation

Use a task branch and PR. Never update `main`, merge, enable auto-merge or use administrator bypass, even with owner credentials. Only the human owner merges; preserve any stricter local protection policy. Keep upstream commit conventions and required sign-offs. Run checks appropriate to the change and report actual results and gaps. Component releases supply packages; installed printers receive only distribution-approved updates with pinned versions. A component update alone does not authorize deployment.

Use concise, specific prose and the `humanizer` skill. Use past-tense PR titles and change summaries, retaining any required Conventional Commit prefix. Follow the [PR policy](https://github.com/carmanspb/k2-unlocked/blob/main/docs/development/pull-requests.md): Summary with Problem and Solution, Key Changes, Testing & Verification, and applicable Screenshots or Risks & Deployment Notes. Link a real related issue when relevant; omit empty sections and owner-review/merge boilerplate.

After opening a PR or pushing a fix, wait two minutes and inspect agent reviews, inline comments, reported bugs and checks. Continue checking roughly every two minutes while review is running. Fix valid findings, validate and push, reply to each specific review comment, and resolve only addressed threads. Do not replace inline replies with a general PR comment.

Never commit personal/account data, machine-specific build paths, secrets, printer identifiers or raw backups/logs. Follow the [privacy policy](https://github.com/carmanspb/k2-unlocked/blob/main/docs/development/documentation-privacy.md). Preserve printer identity, calibration, user data and recovery. Live printer changes require authorization for that task.
