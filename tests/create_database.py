# Add the project root directory to the Python path
import os
import sys
from dotenv import load_dotenv
from app import create_app, db

# Load .flaskenv from the parent directory of the script
dotenv_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".flaskenv")
)
load_dotenv(dotenv_path)

# Add the parent directory of the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

app = create_app()

with app.app_context():
    db.create_all()
    print(f"✅ Tables created in: {app.config['SQLALCHEMY_DATABASE_URI']}")
