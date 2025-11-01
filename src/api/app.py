from flask import Flask

from .routes.rate import rate_bp
from .routes.crud import crud_bp


def create_app():
    # basic app factory, just registers blueprints
    app = Flask(__name__)
    app.register_blueprint(rate_bp)
    app.register_blueprint(crud_bp)
    return app


# quick local run: python -m api.app
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
