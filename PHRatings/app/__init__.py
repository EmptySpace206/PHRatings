from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='../test',
                static_folder='../test')
    app.config.from_object(config_class)

    db.init_app(app)

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # REMOVED: db.create_all() - now handled by scripts/init_db.py

    return app