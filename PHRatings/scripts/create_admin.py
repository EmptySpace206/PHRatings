"""Run this script directly on the server to create admin accounts"""
import sys
import os

# Add the parent directory to the Python path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, Admin

app = create_app()

with app.app_context():
    # Check if database is initialized
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        print("ERROR: Database not initialized!")
        print("Please run 'python scripts/init_db.py' first to create the database.")
        sys.exit(1)
    
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")
    
    if Admin.query.filter_by(username=username).first():
        print("Admin already exists!")
    else:
        admin = Admin(username=username)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully!")