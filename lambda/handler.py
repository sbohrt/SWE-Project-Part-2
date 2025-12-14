# lambda/handler.py
import awsgi
from src.swe_project.api.app import create_app

# Build the Flask (WSGI) app
flask_app = create_app()


def handler(event, context):
    """AWS Lambda handler using awsgi for Flask."""
    return awsgi.response(flask_app, event, context)
