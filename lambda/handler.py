from src.swe_project.api.app import create_app
from mangum import Mangum

# Initialize the FastAPI application
app = create_app()

# Initialize the Mangum handler, which translates API Gateway events
# into ASGI (FastAPI) requests and responses.
handler = Mangum(app)
