# Software and OTA update screens

This branch is an interface prototype. Update checks and installation are
simulated only in desktop fixtures. There is no network updater, persistent
automatic-update preference, scheduled installation or production update service
yet. The ARM release package has not been refreshed for this prototype.

## Preview

From the repository root, build once, then launch:

```sh
cmake --build out/host --parallel 4
sh developer-tools/preview.sh --case software-updates --page system
```

Open Software, toggle automatic updates, select Touchscreen and review the
release. Install update opens a confirmation; confirming changes only the
fixture's displayed installed version. It does not restart processes.

Other cases:

```sh
sh developer-tools/preview.sh --case software-check
sh developer-tools/preview.sh --case software-current
sh developer-tools/preview.sh --case software-printing
```

The first case offers Check for updates and then reveals an example update.
The second stays up to date. The third disables installation during a print.
All versions, dates and change descriptions are examples.

## Screen behavior

- Settings → System shows Software instead of Software version. An upward-arrow
  icon appears when any component reports an update. No update-status text is
  added to this entry.
- Software shows the global Automatic updates On/Off switch above a scrollable
  list of installed components. Each row has its installed version and an arrow
  opening its details. Available updates have the same upward-arrow icon.
- Component details show the installed version, its release date, description
  and update status. The available version and release notes appear only in the
  installation dialog, with Install and Cancel actions. The bottom button is Check for updates until an eligible
  update is available, then Install update. Both remain accessible regardless
  of the automatic-update setting. Busy/printing/paused states disable them.
- Installation opens a scrollable Release notes dialog in the manual flow. Returning to the list
  preserves the in-memory preview state. Actual persistence comes with the service.
- K2 OpenKlipper is listed for information; this prototype does not offer to
  update printer control. Future components require their own installation policy.

## Extensible service contract

The screen consumes `platform.software.automatic` and a `components` array.
Each component has a stable, short `id` (up to 31 ASCII letters, digits,
underscores or hyphens), `name`, `installed_version`, `release_version`,
`release_date`, `installed_release_date`, `description`, `summary`, `status`, `update_available` and `can_update`.
Only compatible, verified update candidates may set `update_available` true.
Repository addresses and compatibility rules belong to a service-owned registry,
not to individual screens. The `candidate_available` field is fixture-only.

The production service will register a provider for each supported repository.
A provider supplies installed-version detection, release discovery, compatibility
checks, staging/install behavior and health/rollback checks. Providers must
explicitly declare any system restart or printer-control effects; a component
must not become automatically installable merely by adding a repository URL.
The screen renders components without adding per-repository layouts.

One global Automatic updates switch controls eligible registered providers.
Checking runs after startup once integration identity and printer state are
known, then hourly while idle. Turning automatic updates off leaves manual
checking and installation available. Unknown compatibility blocks installation.
The touchscreen/backend install together; system updates require separate policy.
The independent updater must survive application restarts, preserve configuration,
retain the previous working runtime, and coordinate with print starts from all
interfaces. None of these production behaviors are implemented by the fixture.
