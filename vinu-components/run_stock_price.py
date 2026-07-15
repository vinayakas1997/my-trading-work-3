"""Start stock-price service on 8081."""
import uvicorn
from vinu_stock.server.app import create_app

app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8081)
