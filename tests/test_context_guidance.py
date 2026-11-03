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
            ("School transport", "E1", "Transport and fleet", "E1.2 Transport, fleet and mobility"),
            ("Food and catering", "E1", "Food and catering", "E1.5 Food and catering"),
            ("Chemical analysis", "E2", "Chemicals and hazardous substances", "E2.1 Chemicals, hazardous substances and remediation"),
            ("Stormwater systems", "E3", "Water and wastewater", "E3.2 Wastewater, stormwater and water systems"),
            ("Green space maintenance", "E4", "Green space and biodiversity", "E4.1 Green space and ecological management"),
            ("Waste and recycling", "E5", "Waste, reuse and circularity", "E5.1 Waste prevention, reuse and recycling"),
            ("ICT hardware", "E5", "ICT equipment", "E5.3 ICT equipment and lifecycle"),
        ]

        for category, primary, expected_tag, expected_subcategory in cases:
            with self.subTest(category=category):
                result = classify_row(
                    {"Inköpskategori 3": category, "Fakturatext": category},
                    mapping_for(category, primary),
                )
                self.assertIn(expected_tag, result.context_tags)
                self.assertIn(expected_subcategory, result.subcategories)

    def test_none_does_not_become_a_review_prompt_by_default(self):
        category = "Legal services"
        result = classify_row(
            {"Inköpskategori 3": category, "Fakturatext": "Legal advice for ICT hardware"},
            mapping_for(category, "None"),
        )
        self.assertEqual(result.context_tags, ())
        self.assertEqual(result.review_focus, ())
        self.assertEqual(result.subcategories, ())


if __name__ == "__main__":
    unittest.main()
