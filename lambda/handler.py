# lambda/handler.py
from src.swe_project.api.app import create_app
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi

# Build the Flask (WSGI) app
flask_app = create_app()

# Convert WSGI -> ASGI
asgi_app = WsgiToAsgi(flask_app)

# Mangum wraps the ASGI app for Lambda / API Gateway
handler = Mangum(asgi_app)
