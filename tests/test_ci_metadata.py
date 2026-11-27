"""The PR base snapshot must not substitute for the current main branch tip."""

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js is required to exercise workflow JavaScript")
class MetadataTests(unittest.TestCase):
    def test_preparation_uses_live_main_ref_instead_of_stale_pr_base(self):
        source = (ROOT / ".github/workflows/arm-package.yml").read_text()
        metadata = source.split("\n  metadata:\n", 1)[1].split("\n  build:\n", 1)[0]
        script = textwrap.dedent(metadata.split("          script: |\n", 1)[1])
        harness = r'''
const fs = require('node:fs');
const script = JSON.parse(fs.readFileSync(0, 'utf8'));
process.env.PR_NUMBER = '16';
const outputs = {};
const core = {setOutput: (key, value) => {outputs[key] = value;}};
const context = {repo: {owner: 'owner', repo: 'repo'}};
const github = {rest: {
  pulls: {get: async () => ({data: {number: 16, state: 'open', draft: false,
    base: {ref: 'main', sha: 'a'.repeat(40)},
    head: {sha: 'b'.repeat(40), ref: 'fix', repo: {full_name: 'owner/repo'}}}})},
  git: {getRef: async data => {
    if (data.ref !== 'heads/main') throw Error('wrong branch ref');
    return {data: {object: {sha: 'c'.repeat(40)}}};
  }}
}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github', 'context', 'core', script)(github, context, core)
  .then(() => process.stdout.write(JSON.stringify(outputs)))
  .catch(error => {console.error(error); process.exitCode = 1;});
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps(script),
                                capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout)
        self.assertEqual(outputs["base"], "c" * 40)
        self.assertEqual(outputs["head"], "b" * 40)
        self.assertTrue(outputs["active"])
        self.assertTrue(outputs["same_repo"])
