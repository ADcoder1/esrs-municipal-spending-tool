import unittest

from esrs_tool.classifier import MappingEntry, classify_row, normalize_key


def mapping_for(category: str, primary: str) -> dict:
    return {
        normalize_key(category): MappingEntry(
            primary=primary,
            secondary="",
            confidence="Medium",
            comment="",
            source_key=category,
            source_column="Inköpskategori 3",
        )
    }


class ContextGuidanceTests(unittest.TestCase):
    def test_major_co_design_prompts_are_attached_to_matching_categories(self):
        cases = [
            ("School transport", "E1", "Transport and fleet"),
            ("Food and catering", "E1", "Food and catering"),
            ("Chemical analysis", "E2", "Chemicals and hazardous substances"),
            ("Stormwater systems", "E3", "Water and wastewater"),
            ("Green space maintenance", "E4", "Green space and biodiversity"),
            ("Waste and recycling", "E5", "Waste, reuse and circularity"),
            ("ICT hardware", "E5", "ICT equipment"),
        ]

        for category, primary, expected_tag in cases:
            with self.subTest(category=category):
                result = classify_row(
                    {"Inköpskategori 3": category, "Fakturatext": category},
                    mapping_for(category, primary),
                )
                self.assertIn(expected_tag, result.context_tags)

    def test_none_does_not_become_a_review_prompt_by_default(self):
        category = "Legal services"
        result = classify_row(
            {"Inköpskategori 3": category, "Fakturatext": "Legal advice"},
            mapping_for(category, "None"),
        )
        self.assertEqual(result.context_tags, ())
        self.assertEqual(result.review_focus, ())


if __name__ == "__main__":
    unittest.main()
