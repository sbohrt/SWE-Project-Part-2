from src.swe_project.api.app import create_app
from mangum import Mangum

# Initialize the FastAPI application
app = create_app()

# Initialize the Mangum handler, which translates API Gateway events
# into ASGI (FastAPI) requests and responses.
handler = Mangum(app)




# basic local test handler for debugging:
if __name__ == "__main__":
    print("This file is intended to be run by AWS Lambda/Mangum.")