from app import create_app
from app.services.rag import reindex_all

app = create_app()
with app.app_context():
    print(reindex_all())
