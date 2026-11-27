"""Exercise the real status-reporting script with cancelled and completed runs."""

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js is required to exercise workflow JavaScript")
class StatusReportingTests(unittest.TestCase):
    def report(self, build="success", publish="success", *, changed="false", moved=False, stale_pr_base=False, main_moved=False):
        workflow = (ROOT / ".github/workflows/arm-package.yml").read_text()
        report_job = workflow.split("\n  report:\n", 1)[1]
        script = textwrap.dedent(report_job.split("          script: |\n", 1)[1])
        head, base = "a" * 40, "b" * 40
        payload = {
            "script": script,
            "env": {"PR_NUMBER": "16", "EXPECTED_HEAD": head, "EXPECTED_BASE": base,
                    "BUILD_RESULT": build, "PUBLISH_RESULT": publish,
                    "CHANGED": changed, "SAME_REPO": "true"},
            "pr": {"state": "open", "head": {"sha": "c" * 40 if moved else head},
                   "base": {"sha": "c" * 40 if stale_pr_base else base}},
            "main": "c" * 40 if main_moved else base,
        }
        harness = r'''
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
Object.assign(process.env, input.env);
const statuses = [];
const github = {rest: {
  pulls: {get: async () => ({data: input.pr})},
  git: {getRef: async () => ({data: {object: {sha: input.main}}})},
  repos: {createCommitStatus: async status => statuses.push(status)}
}};
const context = {repo: {owner: 'owner', repo: 'repo'}, serverUrl: 'https://github.com', runId: 123};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github', 'context', input.script)(github, context)
  .then(() => process.stdout.write(JSON.stringify(statuses)))
  .catch(error => {console.error(error); process.exitCode = 1;});
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps(payload),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_cancelled_build_does_not_overwrite_replacement_status(self):
        self.assertEqual(self.report(build="cancelled", publish="cancelled"), [])

    def test_cancelled_publication_does_not_report_failure(self):
        self.assertEqual(self.report(publish="cancelled"), [])

    def test_real_build_failure_is_reported(self):
        statuses = self.report(build="failure", publish="skipped")
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["state"], "failure")

    def test_unchanged_validated_head_succeeds(self):
        statuses = self.report()
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["state"], "success")
        self.assertEqual(statuses[0]["sha"], "a" * 40)

    def test_replaced_head_is_not_updated(self):
        self.assertEqual(self.report(moved=True), [])

    def test_stale_pr_base_does_not_block_validated_live_main(self):
        statuses = self.report(stale_pr_base=True)
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["state"], "success")

    def test_real_main_advance_suppresses_stale_report(self):
        self.assertEqual(self.report(main_moved=True), [])
