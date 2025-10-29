"""Initialize the database schema - run this once before first use"""
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db

def init_database():
    """Create all database tables"""
    app = create_app()
    
    with app.app_context():
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            print(f"Database already initialized with tables: {', '.join(existing_tables)}")
            response = input("Recreate all tables? This will DELETE all data! (yes/no): ")
            if response.lower() == 'yes':
                db.drop_all()
                print("Dropped all existing tables.")
                db.create_all()
                print("Database tables recreated successfully!")
            else:
                print("Initialization cancelled.")
        else:
            db.create_all()
            print("Database tables created successfully!")
            print("\nNext step: Run 'python scripts/create_admin.py' to create your first admin account.")

if __name__ == '__main__':
    init_database()