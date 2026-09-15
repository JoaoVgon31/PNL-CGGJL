"""Testes da descoberta e expansão de siglas."""


import unittest



from normalizacao.normalizers.acronyms import discover_acronyms, expand_acronyms


class DiscoverAcronymsTests(unittest.TestCase):
    def test_discovers_definitions_from_case_text(self):
        text = (
            "Computed tomography (CT) was performed. "
            "Endoscopic ultrasound (EUS) confirmed the lesion. "
            "Carcinoembryonic antigen (CEA) was elevated."
        )

        self.assertEqual(
            discover_acronyms(text),
            {
                "CT": "Computed tomography",
                "EUS": "Endoscopic ultrasound",
                "CEA": "Carcinoembryonic antigen",
            },
        )

    def test_selects_only_relevant_suffix(self):
        text = (
            "The patient underwent contrast enhanced "
            "computed tomography (CT)."
        )

        self.assertEqual(
            discover_acronyms(text),
            {"CT": "computed tomography"},
        )

    def test_definitions_are_local_to_each_case(self):
        first_case = "Computed tomography (CT) was performed."
        second_case = "No abbreviation is defined here."

        self.assertEqual(
            discover_acronyms(first_case),
            {"CT": "Computed tomography"},
        )
        self.assertEqual(discover_acronyms(second_case), {})


class ExpandAcronymsTests(unittest.TestCase):
    def test_removes_redundant_parenthesized_abbreviation(self):
        definitions = {"CT": "computed tomography"}

        self.assertEqual(
            expand_acronyms(
                "computed tomography (CT)",
                definitions,
            ),
            "computed tomography",
        )

    def test_expands_later_mentions(self):
        definitions = {"CT": "computed tomography"}

        self.assertEqual(
            expand_acronyms("CT demonstrated a lesion", definitions),
            "computed tomography demonstrated a lesion",
        )

    def test_expands_acronym_before_hyphen(self):
        definitions = {"EUS": "endoscopic ultrasound"}

        self.assertEqual(
            expand_acronyms("EUS-guided drainage", definitions),
            "endoscopic ultrasound-guided drainage",
        )

    def test_preserves_unknown_acronym(self):
        definitions = {"CT": "computed tomography"}

        self.assertEqual(
            expand_acronyms("MRI was performed", definitions),
            "MRI was performed",
        )


if __name__ == "__main__":
    unittest.main()