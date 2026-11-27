"""Metadata edits must not queue another expensive package validation."""

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js is required to exercise workflow JavaScript")
class DispatchTests(unittest.TestCase):
    def dispatch(self, event, action=None, changes=None):
        source = (ROOT / ".github/workflows/refresh-pr-packages.yml").read_text()
        script = textwrap.dedent(source.split("          script: |\n", 1)[1])
        payload = {"script": script, "event": event, "action": action, "changes": changes}
        harness = r'''
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const pr = {number: 16, state: 'open', draft: false, base: {ref: 'main'}, head: {sha: 'a'.repeat(40)}};
const github = {
  paginate: async () => [pr],
  rest: {
    pulls: {get: async () => ({data: pr}), list: () => {}},
    repos: {createCommitStatus: async () => calls.push('pending')},
    actions: {createWorkflowDispatch: async data => calls.push(data.inputs.pr_number)}
  }
};
const context = {eventName: input.event, repo: {owner: 'owner', repo: 'repo'},
  payload: {action: input.action, changes: input.changes, pull_request: {number: 16}}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github', 'context', input.script)(github, context)
  .then(() => process.stdout.write(JSON.stringify(calls)))
  .catch(error => {console.error(error); process.exitCode = 1;});
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps(payload),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_body_and_title_edits_do_not_change_status_or_dispatch(self):
        for field in ("body", "title"):
            with self.subTest(field=field):
                self.assertEqual(self.dispatch("pull_request_target", "edited", {field: {"from": "old"}}), [])

    def test_base_change_dispatches_validation(self):
        self.assertEqual(self.dispatch("pull_request_target", "edited", {"base": {"ref": {"from": "other"}}}), ["pending", "16"])

    def test_source_push_dispatches_validation(self):
        self.assertEqual(self.dispatch("pull_request_target", "synchronize"), ["pending", "16"])

    def test_every_main_push_dispatches_validation(self):
        self.assertEqual(self.dispatch("push"), ["pending", "16"])
