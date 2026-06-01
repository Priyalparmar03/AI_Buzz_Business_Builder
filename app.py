import os
from dotenv import load_dotenv
load_dotenv()  # load .env in local dev; no-op on Railway (uses env vars directly)

from flask import Flask, send_from_directory
from config import ActiveConfig
from models import db
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt

# Initialize extensions (not bound to app yet)
bcrypt = Bcrypt()
jwt = JWTManager()


def create_app(config_class=ActiveConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Bind extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Ensure generated_sites directory exists
    os.makedirs(app.config["GENERATED_SITES_DIR"], exist_ok=True)

    # Register blueprints
    from routes.auth import auth as auth_bp
    from routes.generate import generate as generate_bp
    from routes.history import history as history_bp
    from routes.regenerate import regenerate as regenerate_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(generate_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(regenerate_bp, url_prefix="/api")

    # Serve generated websites statically
    @app.route("/sites/<project_id>/")
    @app.route("/sites/<project_id>/index.html")
    def serve_site(project_id):
        site_dir = os.path.join(app.config["GENERATED_SITES_DIR"], project_id)
        if not os.path.exists(os.path.join(site_dir, "index.html")):
            return "<h1>Site not found</h1>", 404
        return send_from_directory(site_dir, "index.html")

    @app.route("/")
    def home():
        return {"status": "ok", "message": "AI Business Builder API is running"}

    # Create tables
    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=5000)