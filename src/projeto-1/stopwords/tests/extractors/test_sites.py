import unittest

from stopwords.extractors.sites import extract_sites


class ExtractSitesTests(unittest.TestCase):
    def test_extracts_known_organ(self):
        text = "a 6cm cystic lesion between the stomach and body/tail of the pancreas"
        mentions = extract_sites(text)
        labels = [m.label for m in mentions]
        self.assertIn("stomach", labels)
        self.assertIn("pancreas", labels)

    def test_detects_laterality(self):
        text = "SAH in her right Sylvian fissure"
        mentions = extract_sites(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["laterality"], "right")

    def test_no_known_organ_no_mentions(self):
        self.assertEqual(extract_sites("The patient felt better."), [])

    def test_no_laterality_bleed_over(self):
        """Verify laterality from one site doesn't bleed into the next site."""
        text = "right kidney, spleen"
        mentions = extract_sites(text)
        self.assertEqual(len(mentions), 2)
        labels = [m.label for m in mentions]
        self.assertIn("kidney", labels)
        self.assertIn("spleen", labels)

        kidney_mention = next(m for m in mentions if m.label == "kidney")
        spleen_mention = next(m for m in mentions if m.label == "spleen")

        self.assertEqual(kidney_mention.attributes["laterality"], "right")
        self.assertIsNone(spleen_mention.attributes["laterality"])

    def test_no_qualifier_bleed_over(self):
        """Verify region_qualifier from one site doesn't bleed into the next site."""
        text = "upper stomach, pancreas"
        mentions = extract_sites(text)
        self.assertEqual(len(mentions), 2)
        labels = [m.label for m in mentions]
        self.assertIn("stomach", labels)
        self.assertIn("pancreas", labels)

        stomach_mention = next(m for m in mentions if m.label == "stomach")
        pancreas_mention = next(m for m in mentions if m.label == "pancreas")

        self.assertEqual(stomach_mention.attributes["region_qualifier"], "upper")
        self.assertIsNone(pancreas_mention.attributes["region_qualifier"])

    def test_no_false_qualifier_from_substring(self):
        """Verify qualifier matching uses word boundaries, not substring matching."""
        text = "after supper the stomach pain began"
        mentions = extract_sites(text)
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0].label, "stomach")
        self.assertIsNone(mentions[0].attributes["region_qualifier"])


if __name__ == "__main__":
    unittest.main()
