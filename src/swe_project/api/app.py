# src/swe_project/api/app.py
import logging
import os

from flask import Flask
from flask_cors import CORS

from .routes import crud, rate, ingest, download, health, lineage, cost, license_check


def create_app():
    app = Flask(__name__)

    # SECURITY FIX: Restrict CORS to specific allowed origins
    # Default to localhost for development, override with ALLOWED_ORIGINS env var
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5000")
    origins_list = [origin.strip() for origin in allowed_origins.split(",")]

    CORS(app, origins=origins_list, supports_credentials=True)

    # All API routes are under /api/v1
    app.register_blueprint(health.bp, url_prefix="/api/v1")
    app.register_blueprint(crud.bp, url_prefix="/api/v1")
    app.register_blueprint(rate.bp, url_prefix="/api/v1")
    app.register_blueprint(ingest.bp, url_prefix="/api/v1")
    app.register_blueprint(download.bp, url_prefix="/api/v1")
    app.register_blueprint(lineage.bp, url_prefix="/api/v1")
    app.register_blueprint(cost.bp, url_prefix="/api/v1")
    app.register_blueprint(license_check.bp, url_prefix="/api/v1")

    return app
