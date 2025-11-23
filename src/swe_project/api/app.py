# src/api/app.py
from flask import Flask
from flask_cors import CORS
import logging

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
