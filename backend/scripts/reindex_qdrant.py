from app import create_app
from app.services.rag import reindex_all
from scripts.migrate_db import migrate_database

app = create_app()
migrate_database(app)
with app.app_context():
    print(reindex_all())
