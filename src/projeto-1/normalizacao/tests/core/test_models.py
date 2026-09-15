"""Testes dos modelos de nós e arestas."""


import unittest
from decimal import Decimal



from normalizacao.core.models import Edge, Node, serialize_attributes


class SerializeAttributesTests(unittest.TestCase):
    def test_ignores_empty_attributes(self):
        attributes = {
            "value": Decimal("12476.5"),
            "unit": "ng/mL",
            "interpretation": None,
            "timing": "",
        }

        self.assertEqual(
            serialize_attributes(attributes),
            "value=12476.5; unit=ng/mL",
        )

    def test_serializes_boolean_in_lowercase(self):
        self.assertEqual(
            serialize_attributes({"contrast": True}),
            "contrast=true",
        )


class NodeTests(unittest.TestCase):
    def test_creates_node_row(self):
        node = Node(
            case_id="PMC5137649_01",
            node_id="E1",
            type="Exam",
            label="computed tomography",
            attributes={"modality": "imaging"},
        )

        self.assertEqual(
            node.to_row(),
            {
                "case_id": "PMC5137649_01",
                "node_id": "E1",
                "type": "Exam",
                "label": "computed tomography",
                "attributes": "modality=imaging",
            },
        )

    def test_rejects_id_with_wrong_prefix(self):
        with self.assertRaises(ValueError):
            Node(
                case_id="PMC5137649_01",
                node_id="S1",
                type="Exam",
                label="computed tomography",
            )

    def test_rejects_empty_label(self):
        with self.assertRaises(ValueError):
            Node(
                case_id="PMC5137649_01",
                node_id="E1",
                type="Exam",
                label="",
            )


class EdgeTests(unittest.TestCase):
    def test_creates_edge_row(self):
        edge = Edge(
            case_id="PMC5137649_01",
            edge_id="e1",
            source_id="P1",
            target_id="E1",
            relation="UNDERWENT_EXAM",
            attributes={"certainty": "asserted"},
        )

        self.assertEqual(
            edge.to_row(),
            {
                "case_id": "PMC5137649_01",
                "edge_id": "e1",
                "source_id": "P1",
                "target_id": "E1",
                "relation": "UNDERWENT_EXAM",
                "attributes": "certainty=asserted",
            },
        )

    def test_rejects_relation_outside_closed_list(self):
        with self.assertRaises(ValueError):
            Edge(
                case_id="PMC5137649_01",
                edge_id="e1",
                source_id="P1",
                target_id="S1",
                relation="PRESENTS_WITH",
            )

    def test_rejects_invalid_edge_id(self):
        with self.assertRaises(ValueError):
            Edge(
                case_id="PMC5137649_01",
                edge_id="edge1",
                source_id="P1",
                target_id="E1",
                relation="UNDERWENT_EXAM",
            )


if __name__ == "__main__":
    unittest.main()