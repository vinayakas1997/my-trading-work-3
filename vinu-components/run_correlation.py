import uvicorn
from vinu_correlation.server.app import create_app
app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8083)
