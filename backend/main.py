from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.llm import MODEL, answer_question, explain_bottleneck, ollama_available
from backend.metrics import dashboard_data, forecast_data, question_context, today_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="HospitalFlow AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Request failed: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "The request could not be completed."})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {"mode": "local" if ollama_available(refresh=True) else "fallback", "model": MODEL}


@app.get("/api/dashboard")
def dashboard() -> dict:
    return dashboard_data()


@app.get("/api/bottlenecks")
def bottlenecks() -> dict:
    flagged = today_metrics()
    flagged = flagged.loc[flagged["risk"].isin(["Warning", "Critical"])]
    results = []
    modes = set()
    for row in flagged.to_dict(orient="records"):
        evidence = {
            key: row[key]
            for key in (
                "appointments",
                "staff_available",
                "avg_task_minutes",
                "emergency_cases",
                "demand_minutes",
                "capacity_minutes",
                "utilization",
            )
        }
        explanation, mode = explain_bottleneck(evidence)
        modes.add(mode)
        results.append(
            {
                "department": row["department"],
                "risk": row["risk"],
                "evidence": evidence,
                "explanation": explanation,
            }
        )
    return {"mode": "local" if modes == {"local"} else "fallback", "bottlenecks": results}


@app.get("/api/forecast")
def forecast() -> dict:
    return forecast_data()


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    answer, mode = answer_question(request.question, question_context())
    return {"answer": answer, "mode": mode}
