import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from app.services.rag import retrieve, retrieve_many


class RAGEvaluationTests(unittest.TestCase):
    def test_batch_retrieval_keeps_public_deduplicated_results_per_query(self):
        class FakeVector:
            def __init__(self, value):
                self.value = float(value)

            def tolist(self):
                return [self.value, 0.2]

            def __len__(self):
                return 2

        embedder = Mock()
        embedder.embed.side_effect = lambda texts: iter(
            FakeVector(index) for index, _ in enumerate(texts)
        )
        client = Mock()
        client.get_collections.return_value = SimpleNamespace(
            collections=[SimpleNamespace(name="folioport_portfolio")]
        )
        client.query_batch_points.return_value = [
            SimpleNamespace(points=[
                SimpleNamespace(score=0.82, payload={
                    "entity_kind": "project",
                    "entity_id": "21",
                    "title": "Accessible dashboard",
                    "text": "Built accessible dashboards.",
                    "is_public": True,
                }),
                SimpleNamespace(score=0.99, payload={
                    "entity_kind": "experience",
                    "entity_id": "22",
                    "title": "Private record",
                    "text": "Private evidence.",
                    "is_public": False,
                }),
                SimpleNamespace(score=0.78, payload={
                    "entity_kind": "project",
                    "entity_id": "21",
                    "title": "Accessible dashboard",
                    "text": "Duplicate chunk.",
                    "is_public": True,
                }),
            ]),
            SimpleNamespace(points=[
                SimpleNamespace(score=0.74, payload={
                    "entity_kind": "experience",
                    "entity_id": "31",
                    "title": "API platform",
                    "text": "Improved API reliability.",
                    "is_public": True,
                }),
            ]),
        ]

        with Flask(__name__).app_context(), patch(
            "app.services.rag._initialized_collections", set()
        ), patch("app.services.rag._get_client", return_value=client), patch(
            "app.services.rag._get_embedder", return_value=embedder
        ):
            results = retrieve_many(
                ["Build accessible interfaces", "Improve API reliability"],
                limit=2,
                public_only=True,
            )

        self.assertEqual(len(results), 2)
        self.assertEqual([hit["entity_id"] for hit in results[0]], ["21"])
        self.assertEqual([hit["entity_id"] for hit in results[1]], ["31"])
        self.assertEqual(
            [request.query for request in client.query_batch_points.call_args.kwargs["requests"]],
            [[0.0, 0.2], [1.0, 0.2]],
        )

    def test_golden_queries_meet_context_precision_and_recall_targets(self):
        class FakeVector:
            def tolist(self):
                return [0.1, 0.2]

        cases = [
            {
                "query": "Which project used Python and what was its role?",
                "relevant": {("project", "21"), ("skill", "4")},
                "points": [
                    ("project", "21", "Project evidence", True),
                    ("project", "21", "Duplicate project chunk", True),
                    ("skill", "4", "Private skill must be filtered", False),
                    ("skill", "4", "Python skill evidence", True),
                    ("education", "9", "Unrelated education", True),
                ],
            },
            {
                "query": "What degree did the candidate earn?",
                "relevant": {("education", "9")},
                "points": [
                    ("education", "9", "", True),
                    ("education", "9", "BSc degree evidence", True),
                ],
            },
        ]
        embedder = Mock()
        embedder.embed.side_effect = lambda texts: iter([FakeVector()])
        client = Mock()
        client.get_collections.return_value = SimpleNamespace(
            collections=[SimpleNamespace(name="folioport_portfolio")]
        )
        client.query_points.side_effect = [
            SimpleNamespace(points=[
                SimpleNamespace(
                    score=1 - index / 10,
                    payload={
                        "entity_kind": kind,
                        "entity_id": entity_id,
                        "title": f"{kind} record",
                        "text": text,
                        "is_public": is_public,
                    },
                )
                for index, (kind, entity_id, text, is_public) in enumerate(case["points"])
            ])
            for case in cases
        ]

        with Flask(__name__).app_context(), patch(
            "app.services.rag._initialized_collections", set()
        ), patch("app.services.rag._get_client", return_value=client), patch(
            "app.services.rag._get_embedder", return_value=embedder
        ):
            for case in cases:
                with self.subTest(query=case["query"]):
                    hits = retrieve(case["query"], limit=2, public_only=True)
                    actual = {(hit["kind"], str(hit["entity_id"])) for hit in hits}
                    relevant = case["relevant"]
                    true_positives = len(actual & relevant)
                    precision = true_positives / len(actual) if actual else 0
                    recall = true_positives / len(relevant)

                    self.assertGreaterEqual(precision, 0.8)
                    self.assertGreaterEqual(recall, 0.8)


if __name__ == "__main__":
    unittest.main()
