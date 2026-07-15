"""Start news service on 8080."""
import uvicorn
from vinu_news.server.app import create_app

app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8080)
