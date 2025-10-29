from app import create_app

app = create_app()

# REMOVED: init-db CLI command - now handled by scripts/init_db.py

if __name__ == '__main__':
    app.run(debug=True)