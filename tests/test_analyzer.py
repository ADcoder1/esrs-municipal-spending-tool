import unittest
import tempfile
from pathlib import Path

from esrs_tool.analyzer import analyze, export_path
from esrs_tool.classifier import classify_row, load_mapping


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
        self.assertEqual(result["context_prompt_count"], 4)
        self.assertTrue(result["category_export_id"])
        self.assertTrue(export_path(result["export_id"]).exists())
        self.assertTrue(export_path(result["category_export_id"]).exists())

        amounts = {row["code"]: row["value"] for row in result["amount_by_esrs"]}
        self.assertEqual(amounts["E1"], 328000.0)
        self.assertEqual(amounts["E4"], 150000.0)
        self.assertEqual(amounts["E5"], 90000.0)
        self.assertEqual(amounts["None"], 32000.0)

    def test_contextual_review_prompts_are_reported(self):
        result = analyze(
            ROOT / "samples" / "sample_invoices.csv",
            ROOT / "samples" / "sample_mapping.csv",
            max_rows=100,
            export_rows=False,
        )
        cautions = result["caution_counts"]
        self.assertEqual(cautions["Green space and biodiversity"], 1)
        self.assertEqual(cautions["Waste, reuse and circularity"], 1)

    def test_context_prompts_do_not_use_department_names(self):
        mapping = load_mapping(ROOT / "samples" / "sample_mapping.csv")
        legal_row = classify_row(
            {
                "Förvaltning": "Stadsledningsförvaltningen",
                "Inköpskategori 1": "Administrativa tjänster",
                "Inköpskategori 2": "Juridiska tjänster",
                "Fakturatext": "Juridisk rådgivning",
            },
            mapping,
        )
        review_focus = " | ".join(legal_row.review_focus)
        self.assertNotIn("Cleaning", review_focus)
        self.assertEqual(review_focus, "")

    def test_analysis_accepts_a_municipality_column_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invoice_path = Path(temp_dir) / "municipality_export.csv"
            invoice_path.write_text(
                "Local purchasing group,Net total,Invoice detail,Organisation\n"
                "Juridiska tjänster,12500,Advice,Finance\n",
                encoding="utf-8",
            )
            result = analyze(
                invoice_path,
                ROOT / "samples" / "sample_mapping.csv",
                column_mapping={
                    "Inköpskategori 3": "Local purchasing group",
                    "Belopp": "Net total",
                    "Fakturatext": "Invoice detail",
                    "Förvaltning": "Organisation",
                },
                export_rows=False,
            )

        self.assertEqual(result["processed_rows"], 1)
        self.assertEqual(result["total_amount"], 12500.0)
        self.assertEqual(result["none_rows"], 1)


if __name__ == "__main__":
    unittest.main()
