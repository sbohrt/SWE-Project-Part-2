# src/api/app.py
from flask import Flask
from flask_cors import CORS
import logging

def _load_metrics():
    """Import metric modules for registration"""
    from swe_project.metrics import bus_factor
    from swe_project.metrics import code_quality
    from swe_project.metrics import dataset_and_code
    from swe_project.metrics import dataset_quality
    from swe_project.metrics import license
    from swe_project.metrics import performance_claims
    from swe_project.metrics import ramp_up_time
    from swe_project.metrics import size_score

def create_app():
    app = Flask(__name__)

    # Configure CORS to allow requests from React frontend
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
        
    # Register blueprints
    from .routes import crud, rate, ingest, download, health
    app.register_blueprint(health.bp, url_prefix='/api/v1')
    app.register_blueprint(crud.bp, url_prefix='/api/v1')
    app.register_blueprint(rate.bp, url_prefix='/api/v1')
    app.register_blueprint(ingest.bp, url_prefix='/api/v1')
    app.register_blueprint(download.bp, url_prefix='/api/v1')
    
    return app
