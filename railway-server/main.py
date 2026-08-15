import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import vision

app = FastAPI(title="Adjudication Vision Server")


class AnalyseRequest(BaseModel):
    image_b64: str
    plan: str
    context: str = "main"


class AnalyseResponse(BaseModel):
    token: str
    pricing: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.post("/analyse", response_model=AnalyseResponse)
def analyse(req: AnalyseRequest):
    try:
        return vision.analyse(req.image_b64, req.plan, req.context)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
