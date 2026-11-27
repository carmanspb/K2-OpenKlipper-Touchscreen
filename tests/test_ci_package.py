"""Real Git merges and artifact boundaries for pre-merge package automation."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import test_package_installation as package_tests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_package", ROOT / "developer-tools/ci_prepare_package.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        ci.git(self.repo, "init", "-b", "main")
        (self.repo / "src").mkdir()
        (self.repo / "src/value").write_text("original\n")
        (self.repo / ci.PACKAGE).mkdir(parents=True)
        (self.repo / ci.PACKAGE / "VERSION").write_text("original\n")
        self.initial = self.save("initial")
        ci.git(self.repo, "branch", "pr")

    def save(self, message):
        ci.git(self.repo, "add", ".")
        ci.commit(self.repo, message)
        return ci.git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def diverge(self, source_conflict=False):
        ci.git(self.repo, "checkout", "pr")
        (self.repo / "src" / ("value" if source_conflict else "pr")).write_text("PR source\n")
        (self.repo / ci.PACKAGE / "VERSION").write_text("PR package\n")
        head = self.save("PR changes")
        ci.git(self.repo, "checkout", "main")
        (self.repo / "src" / ("value" if source_conflict else "main")).write_text("main source\n")
        (self.repo / ci.PACKAGE / "VERSION").write_text("main package\n")
        base = self.save("main changes")
        return head, base

    def test_generated_conflicts_are_rebuilt_and_merge_is_reproducible(self):
        head, base = self.diverge()
        other = Path(self.tmp.name) / "publication"
        ci.git(self.repo, "clone", "--no-hardlinks", str(self.repo), str(other))
        source = ci.prepare(self.repo, head, base)
        self.assertEqual(source, ci.prepare(other, head, base))
        self.assertEqual((self.repo / "src/pr").read_text(), "PR source\n")
        self.assertEqual((self.repo / "src/main").read_text(), "main source\n")
        self.assertEqual((self.repo / ci.PACKAGE / "VERSION").read_text(), "PR package\n")
        parents = ci.git(self.repo, "show", "-s", "--format=%P", "HEAD").stdout.split()
        self.assertEqual(parents, [head, base])
        self.assertEqual(ci.git(self.repo, "status", "--porcelain").stdout, "")

    def test_source_conflict_stops_without_resolving_user_code(self):
        head, base = self.diverge(source_conflict=True)
        with self.assertRaisesRegex(ValueError, "Source conflict"):
            ci.prepare(self.repo, head, base)
        self.assertEqual(ci.git(self.repo, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual((self.repo / "src/value").read_text(), "PR source\n")
        self.assertEqual(ci.git(self.repo, "status", "--porcelain").stdout, "")

    def test_current_branch_does_not_create_a_sync_commit(self):
        self.assertEqual(ci.prepare(self.repo, self.initial, self.initial), self.initial)

    def test_dirty_checkout_is_preserved(self):
        (self.repo / "src/value").write_text("unsaved user edit\n")
        with self.assertRaisesRegex(ValueError, "clean checkout"):
            ci.prepare(self.repo, self.initial, self.initial)
        self.assertEqual((self.repo / "src/value").read_text(), "unsaved user edit\n")


class InstallTests(unittest.TestCase):
    write_manifest = package_tests.PackageChecks.write_manifest

    def setUp(self):
        package_tests.PackageChecks.setUp(self)
        ci.git(self.source, "init", "-b", "pr")
        ci.git(self.source, "add", ".")
        ci.commit(self.source, "source fixture")
        self.recorded = ci.git(self.source, "rev-parse", "HEAD").stdout.strip()
        self.manifest["built_from_commit"] = self.recorded
        self.write_manifest()
        ci.git(self.source, "add", ".")
        ci.commit(self.source, "record package provenance")
        self.head = ci.git(self.source, "rev-parse", "HEAD").stdout.strip()
        self.artifact = self.project / "download"
        shutil.copytree(self.package, self.artifact)
        (self.artifact / "openklipper-screen").chmod(0o644)

    def update_artifact(self):
        path = self.artifact / "assets/nav-house-56.png"
        path.write_text("new generated resource\n")
        manifest = json.loads((self.artifact / "manifest.json").read_text())
        manifest["files"]["assets/nav-house-56.png"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.artifact / "manifest.json").write_text(json.dumps(manifest))

    def test_unchanged_package_is_a_noop_after_artifact_permission_loss(self):
        self.assertEqual(ci.install(self.source, self.artifact, self.project), self.head)
        self.assertEqual(ci.git(self.source, "status", "--porcelain").stdout, "")

    def test_commit_contains_only_validated_package_changes(self):
        self.update_artifact()
        result = ci.install(self.source, self.artifact, self.project)
        self.assertNotEqual(result, self.head)
        paths = ci.git(self.source, "diff", "--name-only", self.head, result).stdout.splitlines()
        self.assertTrue(paths)
        self.assertTrue(all(path.startswith(ci.PACKAGE + "/") for path in paths))
        self.assertEqual(ci.install(self.source, self.artifact, self.project), result)

    def test_unexpected_artifact_files_are_rejected_without_modifying_checkout(self):
        (self.artifact / "payload.py").write_text("raise RuntimeError('must not execute')")
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            ci.install(self.source, self.artifact, self.project)
        self.assertEqual(ci.git(self.source, "status", "--porcelain").stdout, "")

    def test_symlinks_and_corrupted_payload_are_rejected(self):
        icon = self.artifact / "assets/nav-house-56.png"
        icon.unlink()
        icon.symlink_to(self.project / "install.sh")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            ci.install(self.source, self.artifact, self.project)
        icon.unlink()
        icon.write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "checksum"):
            ci.install(self.source, self.artifact, self.project)

    def test_build_provenance_must_be_in_the_pr_history(self):
        manifest = json.loads((self.artifact / "manifest.json").read_text())
        manifest["built_from_commit"] = "0" * 40
        (self.artifact / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "PR history"):
            ci.install(self.source, self.artifact, self.project)
