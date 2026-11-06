"""End-to-end tests for the Onramp scripts against the tinyshop fixture.

Run from the repo root:  python -m unittest discover -s tests -v
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "skills", "onramp", "scripts")
sys.path.insert(0, SCRIPTS)

import render  # noqa: E402
import scan  # noqa: E402
import verify  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="onramp-test-")
        self.repo = os.path.join(self.tmp, "tinyshop")
        shutil.copytree(os.path.join(HERE, "fixtures", "tinyshop"), self.repo)
        os.makedirs(os.path.join(self.repo, ".onramp"))
        self.guide_path = os.path.join(self.repo, ".onramp", "guide.json")
        shutil.copy(os.path.join(HERE, "fixtures", "tinyshop_guide.json"), self.guide_path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def guide(self):
        with open(self.guide_path, encoding="utf-8") as fh:
            return json.load(fh)

    def write_guide(self, g):
        with open(self.guide_path, "w", encoding="utf-8") as fh:
            json.dump(g, fh)

    def run_verify(self, fix=False):
        return verify.verify(self.repo, self.guide_path, fix=fix)


class ScanTest(Fixture):
    def test_inventory_and_graph(self):
        data = scan.scan(self.repo)
        files = {f["path"]: f for f in data["files"]}
        self.assertIn("app/store.py", files["app/server.py"]["imports"])
        self.assertIn("app/models.py", files["app/store.py"]["imports"])
        self.assertEqual(files["tests/test_store.py"]["kind"], "test")
        self.assertEqual(files["README.md"]["kind"], "doc")
        self.assertEqual(files["app/store.py"]["imported_by"], 2)
        langs = {l["lang"] for l in data["languages"]}
        self.assertTrue({"Python", "JavaScript"} <= langs)
        self.assertIn("app/server.py", {e["path"] for e in data["entrypoints"]})
        self.assertIn("SHOP_DATA", {e["name"] for e in data["env_vars"]})

    def test_python_imports_on_consecutive_lines(self):
        with open(os.path.join(self.repo, "app", "both.py"), "w") as fh:
            fh.write("from json import dumps\nfrom .store import Store\nfrom . import models\n")
        files = {f["path"]: f for f in scan.scan(self.repo)["files"]}
        self.assertEqual(files["app/both.py"]["imports"], ["app/models.py", "app/store.py"])


class VerifyTest(Fixture):
    def test_fixture_guide_is_clean(self):
        rep, res = self.run_verify()
        self.assertEqual(rep.errors, [])
        self.assertEqual(res["verified"], res["citations"])
        self.assertGreater(res["citations"], 20)
        self.assertEqual(self.guide()["verification"]["citations"], res["citations"])

    def test_drifted_lines_are_reported_then_fixed(self):
        g = self.guide()
        good = "[[app/store.py:29-38|def place_order(self, skus):]]"
        drifted = "[[app/store.py:33-42|def place_order(self, skus):]]"
        g["flows"][0]["steps"][3]["at"] = drifted
        self.write_guide(g)
        rep, _ = self.run_verify(fix=False)
        self.assertTrue(any("drifted" in e for e in rep.errors), rep.errors)
        rep, res = self.run_verify(fix=True)
        self.assertEqual(rep.errors, [])
        self.assertEqual(res["auto_fixed"], 1)
        self.assertEqual(self.guide()["flows"][0]["steps"][3]["at"], good)

    def test_invented_anchor_fails(self):
        g = self.guide()
        g["lessons"][0]["body"] += " Orders are retried [[app/store.py:29-38|def retry_order(]]."
        self.write_guide(g)
        rep, _ = self.run_verify(fix=True)
        self.assertTrue(any("not in app/store.py" in e for e in rep.errors), rep.errors)
        self.assertNotIn("verification", self.guide())

    def test_missing_file_and_missing_anchor_fail(self):
        g = self.guide()
        g["lessons"][0]["body"] += " See [[app/payments.py]] and [[app/store.py:29-38]]."
        self.write_guide(g)
        rep, _ = self.run_verify()
        joined = "\n".join(rep.errors)
        self.assertIn("does not exist: app/payments.py", joined)
        self.assertIn("needs an anchor", joined)

    def test_structure_errors(self):
        g = self.guide()
        g["lessons"][1]["chapter"] = "nowhere"
        g["lessons"][2]["tier"] = "epic"
        g["lessons"][3]["id"] = g["lessons"][0]["id"]
        g["lessons"][5]["show"] = [{"view": "flow", "id": "no-such-flow"}]
        self.write_guide(g)
        joined = "\n".join(self.run_verify()[0].errors)
        for needle in ("chapter must be one of", "tier must be", "duplicate id", "unknown flow"):
            self.assertIn(needle, joined)

    def test_merge_fragments(self):
        work = os.path.join(self.repo, ".onramp", "work")
        os.makedirs(work)
        with open(os.path.join(work, "files.extra.json"), "w") as fh:
            json.dump([{"path": "web/index.html", "role": "The page shell.", "summary": "Loads [[web/app.js]]."}], fh)
        rep, _ = verify.verify(self.repo, self.guide_path, merge=True)
        self.assertEqual(rep.errors, [])
        self.assertIn("web/index.html", [f["path"] for f in self.guide()["files"]])


class RenderTest(Fixture):
    def test_render_embeds_real_code(self):
        scan_data = scan.scan(self.repo)
        with open(os.path.join(self.repo, ".onramp", "scan.json"), "w", encoding="utf-8") as fh:
            json.dump(scan_data, fh)
        self.run_verify()
        with redirect_stdout(io.StringIO()):
            render.main([self.repo])
        html = read(os.path.join(self.repo, ".onramp", "index.html"))
        self.assertIn('id="onramp-data"', html)
        self.assertNotIn("/*ONRAMP:", html)
        self.assertNotIn("</script>\n</script>", html)
        payload = html.split('id="onramp-data">', 1)[1].split("</script>", 1)[0]
        data = json.loads(payload)
        snip = data["snippets"]["app/store.py:29-38"]
        real = read(os.path.join(self.repo, "app", "store.py")).splitlines()
        self.assertEqual(snip["code"].splitlines(), real[snip["from"] - 1: snip["from"] - 1 + len(snip["code"].splitlines())])
        md = read(os.path.join(self.repo, ".onramp", "GUIDE.md"))
        self.assertIn("citations verified", md)
        self.assertIn("../app/store.py#L29-L38", md)

    def test_public_render_hides_local_path(self):
        with open(os.path.join(self.repo, ".onramp", "scan.json"), "w", encoding="utf-8") as fh:
            json.dump(scan.scan(self.repo), fh)
        with redirect_stdout(io.StringIO()):
            render.main([self.repo, "--public"])
        html = read(os.path.join(self.repo, ".onramp", "index.html"))
        self.assertNotIn(json.dumps(os.path.abspath(self.repo))[1:-1], html)


if __name__ == "__main__":
    unittest.main()
