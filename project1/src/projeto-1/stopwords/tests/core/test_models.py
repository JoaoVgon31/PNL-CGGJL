import unittest

from stopwords.core.models import ALLOWED_RELATIONS, NODE_PREFIXES, Edge, Node, serialize_attributes


class SerializeAttributesTests(unittest.TestCase):
    def test_skips_none_and_empty(self):
        result = serialize_attributes({"a": "1", "b": None, "c": "", "d": "2"})
        self.assertEqual(result, "a=1; d=2")

    def test_formats_bool_lowercase(self):
        self.assertEqual(serialize_attributes({"flag": True}), "flag=true")


class NodeTests(unittest.TestCase):
    def test_valid_node_round_trips(self):
        node = Node("PMC1234567_01", "S1", "Symptom", "abdominal pain", {"polarity": "present"})
        self.assertEqual(node.to_row(), {
            "case_id": "PMC1234567_01",
            "node_id": "S1",
            "type": "Symptom",
            "label": "abdominal pain",
            "attributes": "polarity=present",
        })

    def test_rejects_bad_case_id(self):
        with self.assertRaises(ValueError):
            Node("bad-id", "S1", "Symptom", "pain")

    def test_rejects_node_id_prefix_mismatch(self):
        with self.assertRaises(ValueError):
            Node("PMC1234567_01", "X1", "Symptom", "pain")

    def test_rejects_empty_label(self):
        with self.assertRaises(ValueError):
            Node("PMC1234567_01", "S1", "Symptom", "   ")

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            Node("PMC1234567_01", "Z1", "NotAType", "pain")


class EdgeTests(unittest.TestCase):
    def test_valid_edge_round_trips(self):
        edge = Edge("PMC1234567_01", "e1", "P1", "S1", "HAS_SYMPTOM")
        self.assertEqual(edge.to_row()["relation"], "HAS_SYMPTOM")

    def test_rejects_unknown_relation(self):
        with self.assertRaises(ValueError):
            Edge("PMC1234567_01", "e1", "P1", "S1", "NOT_A_RELATION")

    def test_rejects_bad_edge_id(self):
        with self.assertRaises(ValueError):
            Edge("PMC1234567_01", "edge-1", "P1", "S1", "HAS_SYMPTOM")


class ContractTests(unittest.TestCase):
    def test_node_prefixes_cover_eleven_entities(self):
        self.assertEqual(len(NODE_PREFIXES), 11)
        self.assertNotIn("Concept", NODE_PREFIXES)

    def test_allowed_relations_has_twelve_and_no_same_as(self):
        self.assertEqual(len(ALLOWED_RELATIONS), 12)
        self.assertNotIn("SAME_AS", ALLOWED_RELATIONS)


if __name__ == "__main__":
    unittest.main()
