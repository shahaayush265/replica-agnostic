import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from _load import ROOT, load

init_replica = load("replica-recon", "init_replica")
build_tokens = load("replica-design", "build_tokens")
batch_diff = load("replica-diff", "batch_diff")
check_bugs = load("replica-test", "check_bugs")
generate_test_plan = load("replica-test", "generate_test_plan")
check_brand = load("replica-brand", "check_brand")
fetch_reviews = load("replica-entrepreneur", "fetch_reviews")
preflight = load("replica-deploy", "preflight")


class TestAntigravityPlugin(unittest.TestCase):
    def test_antigravity_plugin_json_exists_and_valid(self):
        manifest_path = os.path.join(ROOT, "plugin.json")
        self.assertTrue(os.path.isfile(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["name"], "replica-agnostic")
        self.assertIn("description", data)
        self.assertIn("suggestedPrompts", data)
        self.assertEqual(len(data["suggestedPrompts"]), 3)
        self.assertEqual(data["version"], "1.0.0")

    def test_antigravity_rules_agents_md_exists(self):
        rules_path = os.path.join(ROOT, "rules", "AGENTS.md")
        self.assertTrue(os.path.isfile(rules_path))
        with open(rules_path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Clean-Room", text)
        self.assertIn("Rebranding", text)

    def test_skills_directory_has_all_eleven(self):
        skills_dir = os.path.join(ROOT, "skills")
        self.assertTrue(os.path.isdir(skills_dir))
        expected = [
            "replica-recon", "replica-architect", "replica-design", "replica-build",
            "replica-backend", "replica-test", "replica-diff", "replica-entrepreneur",
            "replica-brand", "replica-launch", "replica-deploy"
        ]
        for s in expected:
            skill_md = os.path.join(skills_dir, s, "SKILL.md")
            self.assertTrue(os.path.isfile(skill_md), f"Missing {skill_md}")


class TestInitReplica(unittest.TestCase):
    def test_init_workspace_creates_tree_and_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "replica")
            copied, skipped = init_replica.init_workspace(target_dir=target, app_name="TestApp")
            self.assertTrue(os.path.isdir(os.path.join(target, "screens")))
            self.assertTrue(os.path.isdir(os.path.join(target, "clone-screens")))
            self.assertTrue(os.path.isdir(os.path.join(target, "diffs")))
            self.assertTrue(os.path.isdir(os.path.join(target, "design")))
            self.assertTrue(os.path.isdir(os.path.join(target, "launch")))
            self.assertTrue(os.path.isfile(os.path.join(target, "recon.md")))
            self.assertTrue(os.path.isfile(os.path.join(target, "features.csv")))
            self.assertTrue(os.path.isfile(os.path.join(target, "design", "tokens.json")))
            self.assertTrue(os.path.isfile(os.path.join(target, "launch", "listing.json")))

            # Second run without force should skip existing
            c2, s2 = init_replica.init_workspace(target_dir=target)
            self.assertEqual(len(c2), 0)
            self.assertGreater(len(s2), 0)


class TestBuildTokens(unittest.TestCase):
    def test_generate_css_and_tailwind(self):
        sample = {
            "color": {"bg": "#ffffff", "text": "#111111", "accent": "#2f5bea"},
            "font": {"sans": "Inter, sans-serif"},
            "type": {"sm": {"size": 14, "line": 20, "weight": 400}},
            "space": [0, 4, 8, 16],
            "radius": {"md": 8},
            "shadow": {"card": "0 1px 2px rgba(0,0,0,0.1)"},
        }
        css = build_tokens.generate_css(sample)
        self.assertIn("--color-bg: #ffffff;", css)
        self.assertIn("--font-sans: Inter, sans-serif;", css)
        self.assertIn("--text-sm-size: 14px;", css)
        self.assertIn("--space-1: 4px;", css)
        self.assertIn("--radius-md: 8px;", css)

        tw = build_tokens.generate_tailwind(sample)
        self.assertIn('var(--color-bg)', tw)
        self.assertIn('module.exports = {', tw)


class TestCheckBugs(unittest.TestCase):
    def test_parse_and_audit_bugs(self):
        sample_bugs = """
### BUG-001: Critical data loss in booking flow
- Severity: S1
- Status: open

### BUG-002: Notification email not sent
- Severity: S2
- Status: fixed in c1a2b3

### BUG-003: Button misaligned on mobile
- Severity: S4
- Status: open
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(sample_bugs)
            tmp_path = f.name
        try:
            bugs = check_bugs.parse_bugs(tmp_path)
            self.assertEqual(len(bugs), 3)
            stats = check_bugs.audit_bugs(bugs)
            self.assertEqual(stats["total"], 3)
            self.assertEqual(stats["open"], 2)
            self.assertEqual(stats["fixed"], 1)
            self.assertEqual(stats["by_sev"]["S1"]["open"], 1)
            self.assertEqual(stats["by_sev"]["S2"]["open"], 0)
            self.assertEqual(stats["by_sev"]["S2"]["fixed"], 1)

            with redirect_stdout(io.StringIO()):
                code = check_bugs.main([tmp_path, "--fail-on-blocking"])
            self.assertEqual(code, 1)  # BUG-001 is open S1
        finally:
            os.remove(tmp_path)


class TestGenerateTestPlan(unittest.TestCase):
    def test_parse_flows_and_build_plan(self):
        sample_recon = """
## Flows

F01 Guest books meeting
    S01 -> S02 -> S03
    happy path clicks: 4
    edge: slot taken, time zone differs

F02 Host cancels event
    S04 -> S05
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(sample_recon)
            tmp_path = f.name
        try:
            flows = generate_test_plan.parse_flows(tmp_path)
            self.assertEqual(len(flows), 2)
            self.assertEqual(flows[0]["id"], "F01")
            self.assertEqual(flows[0]["goal"], "Guest books meeting")

            plan = generate_test_plan.build_test_plan(flows, app_name="BookingApp")
            self.assertIn("F01-H1", plan)
            self.assertIn("F01-E1", plan)
            self.assertIn("F02-H1", plan)
        finally:
            os.remove(tmp_path)


class TestCheckBrand(unittest.TestCase):
    def test_evaluate_candidate_and_avoidance(self):
        c = check_brand.evaluate_candidate("CalendlyClone", avoid_list=["Calendly"])
        self.assertTrue(any("Calendly" in w for w in c["warnings"]))

        clean = check_brand.evaluate_candidate("Slotwise", avoid_list=["Calendly"])
        self.assertEqual(clean["name"], "Slotwise")
        self.assertEqual(len(clean["warnings"]), 0)
        self.assertIn("uspto", clean["links"])
        self.assertIn("Slotwise", clean["links"]["uspto"])


class TestFetchReviewsHelpers(unittest.TestCase):
    def test_strip_html_and_write_reviews(self):
        html = "<p>Great app, but <b>pricing</b> is too high! &amp; buggy.</p>"
        clean = fetch_reviews.strip_html(html)
        self.assertEqual(clean, "Great app, but pricing is too high! buggy.")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            tmp_csv = f.name
        try:
            items = [
                {"source": "App Store", "url": "https://example.com/1", "date": "2026-01-01", "rating": "1", "text": "Terrible."},
                {"source": "App Store", "url": "https://example.com/1", "date": "2026-01-01", "rating": "1", "text": "Duplicate."},
                {"source": "Hacker News", "url": "https://example.com/2", "date": "2026-01-02", "rating": "", "text": "Needs improvements."},
            ]
            count = fetch_reviews.write_reviews(items, tmp_csv)
            self.assertEqual(count, 2)  # Duplicated URL dropped
        finally:
            os.remove(tmp_csv)


if __name__ == "__main__":
    unittest.main()
