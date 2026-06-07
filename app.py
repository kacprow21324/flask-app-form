import os

from flask import Flask
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from api import init_api
from core.admin import admin_bp
from core.auth import auth_bp, init_oauth, login_manager
from core.config import Config
from core.health import health_bp
from core.models import db
from core.observability import init_observability, metrics_bp
from core.security import init_security
from core.web import DATA_DIR, documents_bp, forms_bp, main_bp, operations_bp


def _register_legacy_url_aliases(app):
    """Pozwala zachować dotychczasowe wywołania url_for bez duplikacji tras."""
    rules = list(app.url_map.iter_rules())
    for rule in rules:
        if "." not in rule.endpoint:
            continue
        blueprint_name, endpoint_name = rule.endpoint.split(".", 1)
        if blueprint_name not in {"main", "documents", "forms", "operations"}:
            continue
        if endpoint_name in app.view_functions:
            continue
        app.add_url_rule(
            rule.rule,
            endpoint=endpoint_name,
            defaults=rule.defaults,
            subdomain=rule.subdomain,
            build_only=True,
        )


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    if app.config["TRUST_PROXY_HEADERS"]:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1,
        )

    init_security(app)
    init_observability(app)
    db.init_app(app)
    Migrate(app, db, compare_type=True)
    login_manager.init_app(app)
    init_oauth(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(forms_bp)
    app.register_blueprint(operations_bp)
    init_api(app)
    _register_legacy_url_aliases(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=app.config["DEBUG"],
    )
