import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from flask import Flask
from flask_jwt_extended import create_access_token
from werkzeug.datastructures import FileStorage

from app.extensions import db, jwt
from app.models import Education, Experience, Profile, Project, Skill
from app.routes.admin import admin_bp
from app.services.document_parser import DocumentParseError, parse_uploaded_resume
from app.services.resume_import import extract_resume_data, infer_skill_category, normalize_resume_data


class ResumeImportTests(unittest.TestCase):
    def test_section_resume_parse_uses_a_tighter_token_budget(self):
        with patch("app.services.resume_import.json_completion", return_value={"skills": []}) as completion:
            result = extract_resume_data("Resume text", [], section="skills")

        self.assertEqual(result, {"skills": []})
        self.assertEqual(completion.call_args.kwargs["max_tokens"], 3500)

    def test_parse_route_returns_editable_preview_without_saving(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, JWT_SECRET_KEY="resume-import-test-secret-longer-than-32")
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()
        extracted = {"profile": {"full_name": "Jordan Example"}, "skills": [], "education": [], "projects": [], "experience": []}

        with patch(
            "app.routes.admin.parse_uploaded_resume",
            return_value={"text": "Resume text", "links": [{"text": "Source Code", "url": "https://example.com"}]},
        ) as parse, patch("app.routes.admin.extract_resume_data", return_value=extracted) as extract:
            response = client.post(
                "/api/admin/resume/parse",
                data={"file": (BytesIO(b"resume file"), "resume.pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"], extracted)
        extract.assert_called_once_with("Resume text", [{"text": "Source Code", "url": "https://example.com"}], section=None)

    def test_parse_route_extracts_only_the_requested_section(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, JWT_SECRET_KEY="resume-import-test-secret-longer-than-32")
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()

        with patch(
            "app.routes.admin.parse_uploaded_resume",
            return_value={"text": "Resume text", "links": []},
        ), patch("app.routes.admin.extract_resume_data", return_value={"skills": [{"name": "Python"}]}) as extract:
            response = client.post(
                "/api/admin/resume/parse",
                data={"section": "skills", "file": (BytesIO(b"resume file"), "resume.pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"], {"skills": [{"name": "Python"}]})
        extract.assert_called_once_with("Resume text", [], section="skills")

    def test_docx_parser_preserves_hyperlink_heading_and_target(self):
        document = Document()
        document.add_paragraph(
            "Jordan Example is a software developer with experience building full-stack web applications."
        )
        paragraph = document.add_paragraph("Project: Portfolio Platform — ")
        relationship_id = document.part.relate_to(
            "https://github.com/jordan/portfolio",
            RT.HYPERLINK,
            is_external=True,
        )
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), relationship_id)
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "Source Code"
        run.append(text)
        hyperlink.append(run)
        paragraph._p.append(hyperlink)
        buffer = BytesIO()
        document.save(buffer)
        upload = FileStorage(
            stream=BytesIO(buffer.getvalue()),
            filename="resume.docx",
        )

        parsed = parse_uploaded_resume(upload)

        self.assertIn("Jordan Example", parsed["text"])
        self.assertEqual(
            parsed["links"],
            [{"text": "Source Code", "url": "https://github.com/jordan/portfolio"}],
        )

    def test_resume_parser_rejects_text_file_extension(self):
        upload = FileStorage(stream=BytesIO(b"resume text"), filename="resume.txt")
        with self.assertRaisesRegex(DocumentParseError, "Upload a .pdf or .docx resume"):
            parse_uploaded_resume(upload)

    def test_normalizer_preserves_structured_resume_and_drops_unsafe_urls(self):
        parsed = normalize_resume_data({
            "profile": {
                "full_name": "Jordan Example",
                "email": "jordan@example.com",
                "website_url": "javascript:alert(1)",
                "years_experience": "3.5",
            },
            "skills": [{"name": "Python", "category": "Programming", "evidence": "Used in projects"}],
            "education": [{
                "institution": "Example University",
                "degree": "BSc",
                "start_year": "2020",
                "end_year": 2024,
            }],
            "projects": [{
                "name": "Portfolio Platform",
                "custom_fields": [{"type": "Source Code", "value": "https://github.com/jordan/portfolio"}],
            }],
            "experience": [{
                "company": "Example Co",
                "title": "Developer",
                "start_date": "01/2022",
                "is_current": True,
            }],
        })

        self.assertEqual(parsed["profile"]["full_name"], "Jordan Example")
        self.assertEqual(parsed["profile"]["website_url"], "")
        self.assertEqual(parsed["profile"]["years_experience"], 3.5)
        self.assertEqual(parsed["education"][0]["start_year"], 2020)
        self.assertEqual(parsed["projects"][0]["custom_fields"][0], {
            "type": "Source Code",
            "value": "https://github.com/jordan/portfolio",
        })
        self.assertTrue(parsed["experience"][0]["is_current"])

    def test_normalizer_infers_missing_or_other_skill_categories(self):
        parsed = normalize_resume_data({
            "profile": {},
            "skills": [
                {"name": "React", "category": "Other"},
                {"name": "PostgreSQL"},
                {"name": "Python", "category": "Programming"},
                {"name": "Unclassified specialty"},
            ],
            "education": [],
            "projects": [],
            "experience": [],
        })

        self.assertEqual(
            [skill["category"] for skill in parsed["skills"]],
            ["Frontend", "Database", "Programming", "Other"],
        )
        self.assertEqual(infer_skill_category("Data Structures and Algorithms"), "Core Concepts")
        self.assertEqual(infer_skill_category("AI/ML"), "AI / ML")

    def test_normalizer_rejects_incomplete_top_level_shape(self):
        with self.assertRaisesRegex(ValueError, "incomplete resume structure"):
            normalize_resume_data({"profile": {}})

    def test_normalizer_accepts_and_returns_only_requested_section(self):
        parsed = normalize_resume_data(
            {"skills": [{"name": "Python"}]},
            section="skills",
        )

        self.assertEqual(list(parsed), ["skills"])
        self.assertEqual(parsed["skills"][0]["name"], "Python")
        self.assertEqual(parsed["skills"][0]["category"], "Programming")

    def test_import_saves_reviewed_records_atomically_and_keeps_visibility_private(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY="resume-import-test-secret-longer-than-32",
        )
        db.init_app(app)
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            db.create_all()
            db.session.add(Profile(
                id=1,
                full_name="Existing Name",
                headline="Original headline",
                email="existing@example.com",
                public_fields=["full_name"],
            ))
            db.session.commit()
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()
        payload = {
            "profile": {
                "full_name": "   ",
                "email": "",
                "headline": "Updated headline",
            },
            "skills": [{"name": "Python", "category": "Programming", "level": "Advanced"}],
            "education": [],
            "projects": [{
                "name": "Portfolio Platform",
                "description": "A portfolio website.",
                "custom_fields": [{"type": "Source Code", "value": "https://github.com/jordan/portfolio"}],
            }],
            "experience": [{
                "company": "Example Co",
                "title": "Developer",
                "start_date": "01/2022",
                "is_current": True,
                "end_date": "01/2024",
            }],
        }

        with patch("app.routes.admin.sync_entities", return_value={"indexed": 3, "warning": None}) as sync:
            response = client.post(
                "/api/admin/resume/import",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["counts"], {"skills": 1, "education": 0, "projects": 1, "experience": 1})
        self.assertEqual(set(sync.call_args.args[0]), {
            ("skill", 1), ("project", 1), ("experience", 1), ("profile", 1),
        })
        with app.app_context():
            profile = db.session.get(Profile, 1)
            project = Project.query.one()
            experience = Experience.query.one()
            self.assertEqual(profile.full_name, "Existing Name")
            self.assertEqual(profile.email, "existing@example.com")
            self.assertEqual(profile.headline, "Updated headline")
            self.assertNotIn("email", profile.public_fields)
            self.assertEqual(project.custom_fields[0]["type"], "Source Code")
            self.assertEqual(experience.end_date, "")
            db.drop_all()

    def test_import_rolls_back_all_changes_when_a_record_is_invalid(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY="resume-import-test-secret-longer-than-32",
        )
        db.init_app(app)
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            db.create_all()
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()

        response = client.post(
            "/api/admin/resume/import",
            json={
                "profile": {"full_name": "Jordan Example"},
                "skills": [{"name": "Python", "category": "Programming"}],
                "education": [],
                "projects": [],
                "experience": [{
                    "company": "Example Co",
                    "title": "Developer",
                    "start_date": "2022",
                    "is_current": False,
                }],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)
        with app.app_context():
            self.assertIsNone(db.session.get(Profile, 1))
            self.assertEqual(Experience.query.count(), 0)
            db.drop_all()

    def test_selected_delete_is_atomic_and_syncs_only_selected_entities(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY="resume-import-test-secret-longer-than-32",
        )
        db.init_app(app)
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            db.create_all()
            db.session.add_all([
                Skill(name="Python", category="Programming"),
                Skill(name="React", category="Frontend"),
                Skill(name="PostgreSQL", category="Database"),
            ])
            db.session.commit()
            ids = [row.id for row in Skill.query.order_by(Skill.id).all()]
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()
        headers = {"Authorization": f"Bearer {token}"}

        missing = client.delete("/api/admin/skills/bulk", json={"ids": [ids[0], 999]}, headers=headers)
        self.assertEqual(missing.status_code, 404)
        with app.app_context():
            self.assertEqual(Skill.query.count(), 3)

        with patch("app.routes.admin.sync_entities", return_value={"indexed": 0, "warning": None}) as sync:
            response = client.delete("/api/admin/skills/bulk", json={"ids": [ids[0], ids[2]]}, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["deleted"], 2)
        self.assertEqual(sync.call_args.args[0], [("skill", ids[0]), ("skill", ids[2])])
        with app.app_context():
            self.assertEqual([row.id for row in Skill.query.all()], [ids[1]])
            db.drop_all()

    def test_bulk_delete_removes_every_record_and_reports_reindex_failure(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY="resume-import-test-secret-longer-than-32",
        )
        db.init_app(app)
        jwt.init_app(app)
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        with app.app_context():
            db.create_all()
            db.session.add_all([
                Skill(name="Python", category="Programming"),
                Education(institution="Example University"),
                Project(name="Portfolio"),
                Experience(company="Example Co", title="Developer"),
            ])
            db.session.commit()
            token = create_access_token(identity="resume-import-test")
        client = app.test_client()
        headers = {"Authorization": f"Bearer {token}"}

        self.assertEqual(client.delete("/api/admin/skills").status_code, 401)
        with patch(
            "app.routes.admin.reindex_all",
            side_effect=[{"indexed": 0}, {"indexed": 0}, RuntimeError("index unavailable"), {"indexed": 0}],
        ) as reindex:
            responses = [
                client.delete(f"/api/admin/{resource}", headers=headers)
                for resource in ("skills", "education", "projects", "experience")
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual([response.json["deleted"] for response in responses], [1, 1, 1, 1])
        self.assertIsNotNone(responses[2].json["index_warning"])
        self.assertEqual(reindex.call_count, 4)
        with app.app_context():
            self.assertEqual(Skill.query.count(), 0)
            self.assertEqual(Education.query.count(), 0)
            self.assertEqual(Project.query.count(), 0)
            self.assertEqual(Experience.query.count(), 0)
        with patch("app.routes.admin.reindex_all", return_value={"indexed": 0}) as reindex:
            empty_response = client.delete("/api/admin/skills", headers=headers)
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json["deleted"], 0)
        reindex.assert_called_once()
        with app.app_context():
            db.drop_all()


if __name__ == "__main__":
    unittest.main()
