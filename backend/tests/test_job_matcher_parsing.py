import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document
from flask import Flask

from app.extensions import limiter
from app.routes.job_matcher import matcher_bp


class JobMatcherParsingTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(RATELIMIT_ENABLED=False, RATELIMIT_STORAGE_URI="memory://")
        limiter.init_app(app)
        app.register_blueprint(matcher_bp, url_prefix="/api/job-match")
        self.client = app.test_client()

    def test_match_route_rejects_malformed_and_unsupported_job_files(self):
        malformed_pdf = self.client.post(
            "/api/job-match",
            data={"file": (BytesIO(b"not a real PDF"), "job.pdf")},
        )
        unsupported = self.client.post(
            "/api/job-match",
            data={"file": (BytesIO(b"job text"), "job.rtf")},
        )

        self.assertEqual(malformed_pdf.status_code, 400)
        self.assertIn("Could not read this PDF", malformed_pdf.json["error"])
        self.assertEqual(unsupported.status_code, 400)
        self.assertIn("Unsupported file type", unsupported.json["error"])

    def test_match_route_extracts_real_text_before_analysis(self):
        description = (
            "Senior software engineer role requiring Python, SQL, and cloud experience. "
            "The engineer will build reliable APIs, review code, and support production services."
        )
        with patch(
            "app.routes.job_matcher.analyze_job",
            return_value={"score": None, "score_label": "Insufficient evidence"},
        ) as analyze:
            response = self.client.post(
                "/api/job-match",
                data={"file": (BytesIO(description.encode("utf-8")), "job.txt")},
            )

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with(description)

    def test_match_route_extracts_docx_before_analysis(self):
        description = (
            "Senior software engineer role requiring Python, SQL, and cloud experience. "
            "The engineer will build reliable APIs, review code, and support production services."
        )
        document = Document()
        document.add_paragraph(description)
        document_buffer = BytesIO()
        document.save(document_buffer)

        with patch(
            "app.routes.job_matcher.analyze_job",
            return_value={"score": None, "score_label": "Insufficient evidence"},
        ) as analyze:
            response = self.client.post(
                "/api/job-match",
                data={"file": (BytesIO(document_buffer.getvalue()), "job-description.docx")},
            )

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with(description)

    def test_match_route_extracts_legacy_doc_before_analysis(self):
        description = (
            "Senior software engineer role requiring Python, SQL, and cloud experience. "
            "The engineer will build reliable APIs, review code, and support production services."
        )
        with patch(
            "app.services.document_parser.extract_legacy_doc",
        ) as extract, patch(
            "app.routes.job_matcher.analyze_job",
            return_value={"score": None, "score_label": "Insufficient evidence"},
        ) as analyze:
            extract.return_value.text = description
            response = self.client.post(
                "/api/job-match",
                data={"file": (BytesIO(b"legacy Word document"), "job-description.doc")},
            )

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with(description)


if __name__ == "__main__":
    unittest.main()
