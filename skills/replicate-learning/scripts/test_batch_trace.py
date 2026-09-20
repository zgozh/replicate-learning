"""batch_trace: the step timer must produce real numbers, and only real numbers.

Regression source: batch 48's export carried no trustworthy per-step timing (concentrated
message timestamps + a context-compaction event). The timer therefore has to be honest by
construction — it refuses phases it does not know, refuses a duration without a matching
``begin``, and refuses to persist anything that looks like a secret or a prompt.
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_trace as T


class TraceWriterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "trace.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def records(self):
        return T.read_records(self.path)

    def test_phase_pair_records_measured_duration(self):
        T.phase_begin(self.path, "write", ms=1000.0)
        T.phase_end(self.path, "write", ms=4500.0)
        ends = [r for r in self.records() if r.get("event") == "end"]
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]["duration_ms"], 3500)
        self.assertEqual(ends[0]["phase"], "write")

    def test_end_without_begin_is_refused(self):
        with self.assertRaises(SystemExit):
            T.phase_end(self.path, "inject", ms=1000.0)
        self.assertEqual(self.records(), [])

    def test_double_end_is_refused(self):
        T.phase_begin(self.path, "gate", ms=0.0)
        T.phase_end(self.path, "gate", ms=10.0)
        with self.assertRaises(SystemExit):
            T.phase_end(self.path, "gate", ms=20.0)

    def test_unknown_phase_is_refused(self):
        with self.assertRaises(SystemExit):
            T.phase_begin(self.path, "think-hard", ms=0.0)
        self.assertEqual(self.records(), [])

    def test_unknown_fact_key_is_refused(self):
        with self.assertRaises(SystemExit):
            T.set_fact(self.path, "write", "prompt", "整段提示词")
        self.assertEqual(self.records(), [])

    def test_secret_shaped_values_are_refused(self):
        for key, value in (("verify_cmd", "curl -H 'Authorization: api_key=abc'"),
                           ("model", "sk-abcdef123456")):
            with self.subTest(key=key):
                with self.assertRaises(SystemExit):
                    T.set_fact(self.path, "verify", key, value)
        with self.assertRaises(SystemExit):
            T.phase_begin(self.path, "write", ms=0.0, note="DASHSCOPE password=xxx")
        self.assertEqual(self.records(), [])

    def test_fact_values_are_typed_and_persisted_as_jsonl(self):
        T.append_record(self.path, T.start_record("stage3-b48", model="flash"))
        T.set_fact(self.path, "inject", "injected_lines", "778")
        T.set_fact(self.path, "gate", "gate_failed_rules", "D1,D3")
        facts = {r["key"]: r["value"] for r in self.records() if r.get("kind") == "fact"}
        self.assertEqual(facts["injected_lines"], 778)
        self.assertEqual(facts["gate_failed_rules"], "D1,D3")
        raw = io.open(self.path, encoding="utf-8").read().strip().split("\n")
        self.assertTrue(all(json.loads(line) for line in raw))

    def test_numeric_fact_rejects_non_number(self):
        with self.assertRaises(SystemExit):
            T.set_fact(self.path, "gate", "gate_ms", "四秒")


class TraceReportTests(unittest.TestCase):
    def test_report_aggregates_and_names_unmeasured_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "trace.jsonl")
            T.append_record(path, T.start_record("stage3-b48", model="flash"))
            T.phase_begin(path, "write", ms=0.0)
            T.phase_end(path, "write", ms=60000.0)
            T.phase_begin(path, "write", ms=60000.0)
            T.phase_end(path, "write", ms=90000.0)
            T.phase_begin(path, "gate", ms=90000.0)
            T.phase_end(path, "gate", ms=94000.0)
            T.set_fact(path, "gate", "gate_version", "2.30")
            rep = T.report(T.read_records(path))
            self.assertEqual(rep["phases"]["write"]["count"], 2)
            self.assertEqual(rep["phases"]["write"]["total_ms"], 90000)
            self.assertEqual(rep["phases"]["write"]["median_ms"], 45000)
            self.assertIn("write", rep["measured_phases"])
            self.assertIn("prepare", rep["unmeasured_phases"])
            self.assertEqual(rep["facts"]["gate_version"], "2.30")
            self.assertEqual(rep["facts"]["model"], "flash")
            text = T.render(rep)
            self.assertIn("未记录阶段", text)
            self.assertIn("没测 ≠ 零耗时", text)


if __name__ == "__main__":
    unittest.main()
