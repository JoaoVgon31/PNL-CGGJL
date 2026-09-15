import unittest

from stopwords.extractors.treatments import extract_medications, extract_treatments


class ExtractTreatmentsTests(unittest.TestCase):
    def test_extracts_surgery_type(self):
        text = "She underwent a laparoscopic distal pancreatectomy."
        mentions = extract_treatments(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["type"], "surgery")
        self.assertEqual(mentions[0].attributes["status"], "performed")

    def test_detects_planned_status(self):
        text = "A laparoscopic distal pancreatectomy was planned."
        mentions = extract_treatments(text)
        self.assertEqual(mentions[0].attributes["status"], "planned")

    def test_does_not_capture_medication_dosage_as_treatment(self):
        text = "She underwent oseltamivir 75 mg twice daily."
        mentions = extract_treatments(text)
        self.assertEqual(mentions, [])

    def test_trigger_correct_for_active_voice(self):
        text = "She underwent a laparoscopic distal pancreatectomy."
        mentions = extract_treatments(text)
        self.assertEqual(mentions[0].trigger, "underwent")

    def test_trigger_correct_for_passive_voice(self):
        text = "A laparoscopic distal pancreatectomy was planned."
        mentions = extract_treatments(text)
        self.assertEqual(mentions[0].trigger, "was planned")


class ExtractMedicationsTests(unittest.TestCase):
    def test_extracts_dose_and_unit(self):
        text = "oseltamivir 75 mg twice daily, arbidol 0.3 g twice daily"
        mentions = extract_medications(text)
        labels = [m.label for m in mentions]
        self.assertIn("oseltamivir", labels)
        self.assertIn("arbidol", labels)
        first = mentions[0]
        self.assertEqual(first.attributes["dose_value"], "75")
        self.assertEqual(first.attributes["dose_unit"], "mg")
        self.assertEqual(first.attributes["frequency"], "twice daily")

    def test_no_dose_no_mentions(self):
        self.assertEqual(extract_medications("She was given supportive care."), [])


if __name__ == "__main__":
    unittest.main()
