# src/swe_project/api/app.py
from flask import Flask
from flask_cors import CORS

from .routes import crud, rate, ingest, download, health, lineage


def create_app():
    app = Flask(__name__)
    CORS(app)

    # All API routes are under /api/v1
    app.register_blueprint(health.bp, url_prefix="/api/v1")
    app.register_blueprint(crud.bp, url_prefix="/api/v1")
    app.register_blueprint(rate.bp, url_prefix="/api/v1")
    app.register_blueprint(ingest.bp, url_prefix="/api/v1")
    app.register_blueprint(download.bp, url_prefix="/api/v1")
    app.register_blueprint(lineage.bp, url_prefix="/api/v1")

    return app
