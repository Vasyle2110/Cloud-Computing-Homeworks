from app.main import create_app
from app.config import BACKEND_HOST, BACKEND_PORT, DEBUG

app = create_app()

if __name__ == "__main__":
    app.run(
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        debug=DEBUG
    )