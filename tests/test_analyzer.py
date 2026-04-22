import unittest
from pathlib import Path

from esrs_tool.analyzer import analyze, export_path
from esrs_tool.classifier import load_mapping


ROOT = Path(__file__).resolve().parents[1]


class AnalyzerTests(unittest.TestCase):
    def test_sample_mapping_loads(self):
        mapping = load_mapping(ROOT / "samples" / "sample_mapping.csv")
        self.assertGreaterEqual(len(mapping), 5)
        self.assertIn("juridiska tjanster", mapping)
        self.assertEqual(mapping["juridiska tjanster"].primary, "None")

    def test_sample_analysis_classifies_rows(self):
        result = analyze(
            ROOT / "samples" / "sample_invoices.csv",
            ROOT / "samples" / "sample_mapping.csv",
            max_rows=100,
            export_rows=True,
        )
        self.assertEqual(result["processed_rows"], 5)
        self.assertEqual(result["unmatched_rows"], 0)
        self.assertEqual(result["review_count"], 1)
        self.assertTrue(result["category_export_id"])
        self.assertTrue(export_path(result["export_id"]).exists())
        self.assertTrue(export_path(result["category_export_id"]).exists())

        amounts = {row["code"]: row["value"] for row in result["amount_by_esrs"]}
        self.assertEqual(amounts["E1"], 328000.0)
        self.assertEqual(amounts["E4"], 150000.0)
        self.assertEqual(amounts["E5"], 90000.0)
        self.assertEqual(amounts["None"], 32000.0)

    def test_meeting_driven_cautions_are_reported(self):
        result = analyze(
            ROOT / "samples" / "sample_invoices.csv",
            ROOT / "samples" / "sample_mapping.csv",
            max_rows=100,
            export_rows=False,
        )
        cautions = result["caution_counts"]
        self.assertEqual(cautions["Green space needs biodiversity review"], 1)
        self.assertEqual(cautions["Circular spend may need funding-source review"], 1)
        self.assertEqual(cautions["Intentionally outside E1-E5"], 1)


if __name__ == "__main__":
    unittest.main()
