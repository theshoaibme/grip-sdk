"""Main entry point for Grip AI Search server using Grip SDK."""

from google_ai_search.config import get_config
from app.server import create_app

config = get_config()
app = create_app(config)

if __name__ == "__main__":
    print(f"🚀 Starting Grip AI Search server on port {config.port}...")
    app.run(host="0.0.0.0", port=config.port, debug=config.debug)