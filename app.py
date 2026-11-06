import os

from dotenv import load_dotenv

# Before importing the app: app.config.Config reads os.environ at import time.
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    app.run(host=host, port=port)
