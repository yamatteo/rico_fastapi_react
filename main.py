from fastapi import Request
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path


from backend.main import app

@app.get("/")
async def get_index(request: Request):
    return HTMLResponse(content=str(list(Path(".").iterdir())), status_code=200)
    with open("./frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)