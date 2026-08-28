import os

from app import app


if __name__ == "__main__":
    host = os.getenv("LTT_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("LTT_PORT", "5050")))
    app.run(host=host, port=port, debug=False)
