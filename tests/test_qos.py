import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qos_lab import Profile, audit, mismatches


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def case(name):
    return json.loads((EXAMPLES / (name + ".json")).read_text(encoding="utf-8"))


class QosTests(unittest.TestCase):
    def test_cartesian_product_matches_published_policy_tables(self):
        allowed_reliability = {
            ("best_effort", "best_effort"), ("reliable", "best_effort"), ("reliable", "reliable")
        }
        allowed_durability = {
            ("volatile", "volatile"), ("transient_local", "volatile"),
            ("transient_local", "transient_local"),
        }
        rel = ("best_effort", "reliable")
        dur = ("volatile", "transient_local")
        for p_r, p_d, s_r, s_d in itertools.product(rel, dur, rel, dur):
            with self.subTest(p_r=p_r, p_d=p_d, s_r=s_r, s_d=s_d):
                expected = []
                if (p_r, s_r) not in allowed_reliability:
                    expected.append("reliability")
                if (p_d, s_d) not in allowed_durability:
                    expected.append("durability")
                self.assertEqual(mismatches(Profile(p_r, p_d), Profile(s_r, s_d)), expected)

    def test_camera_fix_exposes_live_ids_only(self):
        failed, fixed = (audit(case("camera-" + kind)) for kind in ("mismatch", "compatible"))
        self.assertEqual(failed, dict(compatible_for_modeled_policies=False,
                                    unmet_requests=["reliability"], modeled_replay_ids=[], eligible_live_ids=[]))
        self.assertEqual(fixed, dict(compatible_for_modeled_policies=True,
                                   unmet_requests=[], modeled_replay_ids=[], eligible_live_ids=[104, 105]))

    def test_transient_pair_only_replays_newest_two_old_ids(self):
        result = audit(case("status-late-join"))
        self.assertEqual(result["modeled_replay_ids"], [102, 103])
        self.assertEqual(result["eligible_live_ids"], [104, 105])

    def test_volatile_request_does_not_receive_old_ids(self):
        result = audit(case("status-volatile-reader"))
        self.assertTrue(result["compatible_for_modeled_policies"])
        self.assertEqual(result["modeled_replay_ids"], [])
        self.assertEqual(result["eligible_live_ids"], [104, 105])

    def test_empty_history_and_depth_bigger_than_history(self):
        scenario = case("status-late-join")
        scenario["publisher"]["depth"] = 20
        self.assertEqual(audit(scenario)["modeled_replay_ids"], [101, 102, 103])
        scenario["before_join"] = []
        self.assertEqual(audit(scenario)["modeled_replay_ids"], [])

    def test_two_unmet_requests_block_every_id(self):
        scenario = case("camera-mismatch")
        scenario["subscriber"]["durability"] = "transient_local"
        result = audit(scenario)
        self.assertEqual(result["unmet_requests"], ["reliability", "durability"])
        self.assertEqual(result["modeled_replay_ids"] + result["eligible_live_ids"], [])

    def test_duplicate_at_boundary_is_rejected(self):
        scenario = case("status-late-join")
        scenario["after_join"][0] = 103
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            audit(scenario)

    def test_unsupported_defaults_and_bad_depth_are_rejected(self):
        for value in (False, 0, -2, 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive integer"):
                scenario = case("status-late-join")
                scenario["publisher"]["depth"] = value
                audit(scenario)
        with self.assertRaisesRegex(ValueError, "reliability"):
            Profile("system_default", "volatile")

    def test_cli_reports_duplicate_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"publisher": {}, "publisher": {}}', encoding="utf-8")
            proc = subprocess.run([sys.executable, "qos_lab.py", str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("duplicate field: publisher", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
