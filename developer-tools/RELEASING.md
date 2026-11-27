# Preparing a touchscreen release

Release notes should help someone using the printer understand what changed,
whether they can install it, and anything they need to do. Keep build logs and
implementation details in the linked PRs.

## Choose the release scope

1. Record the target commit and the previous published release's tag and commit.
   Compare against the previous release in the same channel: stable for stable,
   or the preceding prerelease in that preview series. Also call out upgrade
   requirements since stable when publishing a stable release.
2. Review the complete commit range and all merged PRs whose changes are included
   in it. Follow pagination. Check the diff as well as PR descriptions, including
   squash merges, direct commits, reverts and follow-up fixes. Do not include a
   PR just because it was recently merged or has a particular label.
3. Keep a preparation record of the baseline, target and reviewed PRs. Mark each
   as a user-facing feature, improvement, fix, installation/compatibility change,
   or internal change. Combine related PRs into one clear description.
4. For the first release, say there is no previous release. Give a short overview
   of the included interface and highlight recent improvements. Do not invent a
   comparison tag or present the entire interface as a recent addition.

Use the exact release commit for source and screenshot links. Features merged
later, planned work and unsupported hardware capabilities must not appear as
shipped features. Mention absent functionality only when it affects installation
or a reasonable expectation about the release.

## Write the notes

Aim for 250–450 words for updates, excluding image captions and a full-changelog
link. A first release may use up to about 650 words to list the included features
and settings. Small fix releases should be shorter. Use only the sections the
release needs. For a first release, group the feature list by printer task and
include a Settings section naming the available controls and optional components.

- Open with one sentence naming the main change or the purpose of a first release.
- Group changes by the areas users recognize, such as Home and printing,
  Filament and CFS, Movement and bed mesh, or Settings. Put the most useful changes
  first. Use a separate Fixes section when fixes do not fit those groups.
- Write short bullets describing the resulting behavior. Explain where to find
  a new control and any prerequisite or restart it requires.
- Translate PR titles into ordinary language. For example, “Saved light-off and
  idle timers are restored after Klipper restarts” is clearer than “Restore
  persisted timer state after backend initialization.” Avoid hype and vague
  claims such as “improved stability.”
- Link each grouped change to its PR or relevant documentation. Keep CI work,
  dependency maintenance and generated-package updates out of the feature list
  unless they change installation or printer behavior.
- End with short installation, compatibility and known-limitations information.
  State supported K2 OpenKlipper versions, the correct download, upgrade steps
  and any interruption. Link to full instructions rather than duplicating them.
- Link the full comparison for later releases. For the first release, link the
  interface guide instead. Keep an internal preparation record of reviewed work
  even when it is omitted from the public notes.

Do not turn the notes into a copy of the README, a commit dump or a test report.
Separate measured performance results from estimates, and live printer checks
from simulator or automated checks. A build-context version alone is not proof
of installation compatibility.

## Use images sparingly

Use an image when it makes a new feature or changed interaction easier to
understand. Most fix releases need none.

- Normally use one or two screenshots per release; use a third only when a
  separate major feature needs it. Put additional views in the linked guide.
- Place each image beside its feature section, with a short, descriptive caption
  or alt text. Use a side-by-side pair only for a useful comparison.
- Show the released behavior. Verify screenshots against the target commit and
  inspect them for stale labels, misleading examples and personal information.
- Use immutable, commit-pinned URLs that render in GitHub release notes.
  Do not use local paths or links to a mutable feature branch.
- Identify simulator/example data when it could be mistaken for verified hardware
  behavior. Screenshots of several CFS units do not establish driver support.

## Package contents

The downloadable ARM package must contain everything needed for the touchscreen
runtime: the ARM executable, matching Python backend, assets, startup scripts,
required feature helpers, version and checksum metadata, and license notices.
Keep the packaged README very short: link to the main touchscreen guide and
list common commands for starting/restarting the screen, checking uninstall and
uninstalling. Include configuration/log locations and a brief uninstall warning.
Keep detailed features, settings, compatibility and installation steps in the
linked guide and release notes.
Ship installation/migration helpers when the supported installation path needs
them. Preserve printer configuration and display preferences during upgrades.

Exclude desktop builds, simulator fixtures, development tools, test outputs,
screenshots and unrelated documentation from the runtime archive. Keep screenshots
in the repository and reference them from release notes. GitHub's generated
source archives are separate from the installable runtime asset; identify the
correct download explicitly. Keep corresponding source available for GPL-covered
binaries and retain third-party license notices.

A runtime payload that still needs installer integration must remain a draft,
clearly labelled as such. Do not describe it as an installable release or make it
eligible for automatic updates.

## Publication checks

Before publishing:

- Confirm the target commit, version, release channel and notes describe the
  same build. Check that every claimed change is included and not reverted.
- Validate the ARM target, complete file inventory, source provenance and
  checksums. Verify the downloaded release asset, not just the staging directory.
- Verify installation and upgrade on the declared supported integration. Record
  automated checks separately from live printer checks, with their limits.
- Confirm the installer preserves configuration and starts the matching screen
  and backend. Document any required restarts and how to recover from failure.
- Check the rendered notes, screenshot links, headings and downloads. Remove
  empty sections, internal implementation detail and promises about future work.
- Keep the release as a draft until outstanding installation or compatibility
  work is complete. Mark previews as prereleases.

### When online updates become available

These are requirements for future implementation, not current capabilities:

- Check after startup once printer state and the installed integration identity
  are known, then hourly while idle. Defer checks while printing or busy.
- Provide an Automatic updates setting. When it is off, show compatible updates
  with an Install update action. Both installation paths use the same checks.
- Select a newer release from the configured channel only when its compatibility
  metadata explicitly supports the installed K2 OpenKlipper integration. Unknown
  versions or missing/invalid metadata must not be eligible.
- Verify package integrity, recheck fresh idle state and active operations before
  installation, preserve configuration, and retain the previous runtime for
  rollback if the new screen/backend fails its health checks.
- Keep these eligibility checks separate from the human-readable release notes.
  Notes are not a machine-readable compatibility contract.

## Release-notes outline

Replace the placeholders, remove unused sections, and keep only shipped changes.

```markdown
One sentence describing the main change.

## [User-facing area]

- What changed, where to find it, and any prerequisite. ([PR](...))

[Optional screenshot with descriptive alt text]

## Fixes

- The problem users encountered and the corrected behavior. ([PR](...))

## Install and compatibility

Supported K2 OpenKlipper versions, correct runtime download, and a link to
installation instructions. Mention required restarts and known limitations.

[Full changelog](...compare/PREVIOUS_TAG...RELEASE_TAG)
```
