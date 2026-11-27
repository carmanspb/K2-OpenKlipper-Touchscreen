#!/usr/bin/env python3
"""Prepare PR source and install validated CI artifacts without running PR code."""

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "precompiled/armv7"
BOT = ("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com")


def git(repo, *args, check=True, env=None):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        check=check, capture_output=True, text=True, env=env,
    )


def commit(repo, message, timestamp=None):
    env = os.environ.copy()
    if timestamp is not None:
        env.update(GIT_AUTHOR_DATE=f"@{timestamp} +0000", GIT_COMMITTER_DATE=f"@{timestamp} +0000")
    git(repo, *BOT, "commit", "--no-gpg-sign", "-m", message, env=env)


def prepare(repo, head, base):
    for sha in (head, base):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Expected an immutable commit SHA")
    if git(repo, "status", "--porcelain").stdout:
        raise ValueError("Prepare requires a clean checkout")
    git(repo, "checkout", "--detach", head)
    if not git(repo, "merge-base", "--is-ancestor", base, head, check=False).returncode:
        return head
    result = git(repo, *BOT, "merge", "--no-commit", "--no-ff", base, check=False)
    conflicts = git(repo, "diff", "--name-only", "--diff-filter=U", "-z").stdout.split("\0")
    conflicts = [path for path in conflicts if path]
    if result.returncode and (not conflicts or any(not path.startswith(PACKAGE + "/") for path in conflicts)):
        git(repo, "merge", "--abort", check=False)
        raise ValueError("Source conflict: update the PR manually.\n" + result.stdout + result.stderr)
    # Regenerate the package after merging; never guess how source conflicts
    # should be resolved. Restoring the old package also handles deleted assets.
    git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", PACKAGE)
    timestamp = max(int(git(repo, "show", "-s", "--format=%ct", sha).stdout) for sha in (head, base))
    commit(repo, f"Merge main before touchscreen package validation\n\nHead: {head}\nBase: {base}", timestamp)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def install(repo, package, integration):
    # This script lives in the trusted workflow checkout. The write job must
    # never import the validator from the PR or execute artifact contents.
    spec = importlib.util.spec_from_file_location("trusted_package_check", ROOT / "installation/validate_package.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    repo, package = Path(repo), Path(package)
    actual = set()
    for path in package.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Artifact contains a non-regular path")
        if path.is_file():
            actual.add(path.relative_to(package).as_posix())
    # Artifact download does not retain Unix permissions.
    (package / "openklipper-screen").chmod(0o755)
    manifest = validator.validate(repo, package, integration)
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Artifact contains unexpected files")
    recorded = manifest.get("built_from_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", recorded) or git(repo, "merge-base", "--is-ancestor", recorded, "HEAD", check=False).returncode:
        raise ValueError("Package was not built from the prepared PR history")
    for path in (repo / "precompiled", repo / PACKAGE):
        if path.is_symlink():
            raise ValueError("Package destination must not be a symlink")
    shutil.rmtree(repo / PACKAGE)
    shutil.copytree(package, repo / PACKAGE)
    git(repo, "add", "--", PACKAGE)
    if git(repo, "diff", "--cached", "--quiet", check=False).returncode:
        commit(repo, "Refresh ARM package for the current PR source")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "install"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--head")
    parser.add_argument("--base")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--integration-root", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        if not args.head or not args.base:
            parser.error("prepare needs --head and --base")
        sha = prepare(args.repo, args.head, args.base)
    else:
        if not args.package or not args.integration_root:
            parser.error("install needs --package and --integration-root")
        sha = install(args.repo, args.package, args.integration_root)
    print(sha)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"sha={sha}\n")


if __name__ == "__main__":
    main()
