import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from app.services.rag import retrieve, retrieve_many
from app.services.rag_evaluation import judge_answer, retrieval_metrics


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

    def test_golden_queries_compute_entity_level_retrieval_metrics(self):
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
                    scores = retrieval_metrics(
                        hits,
                        [{"kind": kind, "id": entity_id} for kind, entity_id in case["relevant"]],
                        2,
                    )

                    self.assertEqual(scores["precision_at_2"], 1.0 if case["query"].startswith("Which") else 0.5)
                    self.assertEqual(scores["recall_at_2"], 1.0)
                    self.assertEqual(scores["mrr"], 1.0)
                    self.assertEqual(scores["ndcg_at_2"], 1.0)

    def test_retrieval_metrics_reflect_rank_and_fixed_cutoff(self):
        scores = retrieval_metrics(
            [
                {"kind": "project", "entity_id": "unrelated"},
                {"kind": "project", "entity_id": "relevant"},
            ],
            [{"kind": "project", "id": "relevant"}, {"kind": "skill", "id": "missing"}],
            3,
        )

        self.assertAlmostEqual(scores["precision_at_3"], 1 / 3)
        self.assertEqual(scores["recall_at_3"], 0.5)
        self.assertEqual(scores["mrr"], 0.5)
        rank_two_gain = 1 / math.log2(3)
        self.assertAlmostEqual(scores["ndcg_at_3"], rank_two_gain / (1 + rank_two_gain))

    def test_judge_requires_all_bounded_metric_scores(self):
        valid_scores = {
            "context_precision": 0.8,
            "context_recall": 0.75,
            "faithfulness": 1,
            "answer_relevance": 0.9,
            "answer_correctness": 0.8,
        }
        with patch("app.services.rag_evaluation.json_completion", return_value=valid_scores):
            scores = judge_answer("question", "reference", "retrieved", "full context", "answer")
        self.assertEqual(scores["faithfulness"], 1.0)

        with patch(
            "app.services.rag_evaluation.json_completion",
            return_value={**valid_scores, "faithfulness": 1.1},
        ):
            with self.assertRaisesRegex(ValueError, "faithfulness"):
                judge_answer("question", "reference", "retrieved", "full context", "answer")


if __name__ == "__main__":
    unittest.main()
