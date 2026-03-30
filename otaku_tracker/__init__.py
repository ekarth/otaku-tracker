from flask import Flask

from .config import Settings
from .extensions import db, migrate
from .filters import register_filters


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    settings = Settings()
    app.config["SECRET_KEY"] = settings.flask_secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    register_filters(app)

    from .routes.main import bp as main_bp
    from .routes.entries import bp as entries_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(entries_bp)

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        print("Database tables created.")

    return app
