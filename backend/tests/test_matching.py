import unittest
from unittest.mock import patch

from flask import Flask

from app.services.ai import AIServiceError
from app.services.matching import (
    _candidate_years,
    _contains_term,
    _corpus_from_bundle,
    _extract_jd,
    _normalized_requirements,
    analyze_job,
)


def extracted_job(required=None, preferred=None, responsibilities=None, experience=None, education=None):
    return {
        "title": "Software Engineer",
        "company": "",
        "seniority": "",
        "summary": "",
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "responsibilities": responsibilities or [],
        "experience_requirements": experience or [],
        "education_requirements": education or [],
        "keywords": [],
    }


class JobMatchingTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.description = "Software engineer role with responsibilities and requirements. " * 2
        self.empty_bundle = {
            "profile": {},
            "skills": [],
            "projects": [],
            "experience": [],
            "education": [],
        }

    def analyze(self, extracted, bundle=None, semantic_hits=None):
        with self.app.app_context(), patch(
            "app.services.matching.json_completion", return_value=extracted
        ), patch(
            "app.services.matching.get_portfolio_bundle",
            return_value=bundle or self.empty_bundle,
        ) as get_bundle, patch(
            "app.services.matching.retrieve",
            return_value=semantic_hits or [],
        ) as retrieve:
            result = analyze_job(self.description)
        return result, get_bundle, retrieve

    def test_only_saved_skill_names_are_exact_matches(self):
        bundle = {
            "profile": {
                "full_name": "Candidate",
                "public_fields": ["full_name"],
                "email": "private@example.test",
            },
            "skills": [{"id": 1, "name": "JavaScript", "category": "Programming"}],
            "projects": [{
                "id": 2,
                "name": "Data tool",
                "description": "Used Python to automate data cleanup.",
            }],
            "experience": [],
            "education": [],
        }
        result, get_bundle, retrieve = self.analyze(
            extracted_job(required=[
                {"skill": "JS", "importance": "high", "evidence": "JavaScript"},
                {"skill": "Python", "importance": "normal", "evidence": "Python"},
            ]),
            bundle=bundle,
        )

        self.assertEqual([item["skill"] for item in result["matched_skills"]], ["JS"])
        self.assertEqual([item["skill"] for item in result["related_skills"]], ["Python"])
        self.assertEqual(result["unmatched_skills"], [])
        self.assertEqual(result["score"], 78)
        get_bundle.assert_called_once_with(public_only=True)
        retrieve.assert_not_called()
        evidence = result["related_skills"][0]["related_evidence"][0]["text"]
        self.assertIn("Python", evidence)
        self.assertNotIn("private@example.test", evidence)

    def test_semantic_results_must_be_public_and_above_threshold(self):
        result, _, retrieve = self.analyze(
            extracted_job(required=[
                {"skill": "Kubernetes", "importance": "critical", "evidence": "Kubernetes"}
            ]),
            semantic_hits=[
                {"title": "Private record", "text": "Kubernetes", "score": 0.99, "is_public": False},
                {"title": "Weak public result", "text": "Kubernetes", "score": 0.47, "is_public": True},
            ],
        )

        self.assertEqual(result["unmatched_skills"][0]["skill"], "Kubernetes")
        self.assertEqual(result["score"], 0)
        retrieve.assert_called_once_with("Kubernetes", limit=6, public_only=True)

    def test_no_measurable_requirements_returns_no_score(self):
        result, _, _ = self.analyze(extracted_job())

        self.assertIsNone(result["score"])
        self.assertEqual(result["score_label"], "Insufficient evidence")
        self.assertEqual(result["score_breakdown"], {})

    def test_requirement_aliases_are_deduplicated_and_importance_is_validated(self):
        requirements = _normalized_requirements([
            {"skill": "Node.js", "importance": "critical"},
            {"skill": "nodejs", "importance": ["invalid"]},
            {"skill": "Python", "importance": "invented"},
        ], limit=20)

        self.assertEqual([item["skill"] for item in requirements], ["Node.js", "Python"])
        self.assertEqual([item["importance"] for item in requirements], ["critical", "normal"])

    def test_ambiguous_go_term_does_not_match_ordinary_prose(self):
        self.assertFalse(_contains_term("We are ready to go to market.", "Go"))
        self.assertTrue(_contains_term("Built services with Golang.", "Go"))

    def test_incomplete_requirement_extraction_is_rejected(self):
        with patch(
            "app.services.matching.json_completion",
            return_value={"required_skills": []},
        ), self.assertRaises(AIServiceError):
            _extract_jd(self.description)

    def test_profile_corpus_includes_only_fields_marked_public(self):
        records = _corpus_from_bundle({
            "profile": {
                "full_name": "Candidate",
                "email": "private@example.test",
                "public_fields": ["full_name"],
            },
            "skills": [],
            "projects": [],
            "experience": [],
            "education": [],
        })

        corpus = " ".join(record["text"] for record in records)
        self.assertIn("Candidate", corpus)
        self.assertNotIn("private@example.test", corpus)

    def test_overlapping_experience_intervals_are_not_double_counted(self):
        years = _candidate_years({
            "profile": {"years_experience": 0},
            "experience": [
                {"start_date": "01/2020", "end_date": "12/2020", "is_current": False},
                {"start_date": "07/2020", "end_date": "06/2021", "is_current": False},
            ],
        })

        self.assertAlmostEqual(years, 1.5)


if __name__ == "__main__":
    unittest.main()
