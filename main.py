from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import time
import certifi
from fastapi.responses import FileResponse, Response
import logging

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME must be set in .env")

client = AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where())
db = client[DB_NAME]


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    company: str | None = None
    reason: str | None = None
    message: str


class AnalyticsEvent(BaseModel):
    type: str
    path: str
    referrer: str | None = None


@app.post("/api/contact", status_code=201)
async def contact(form: ContactForm, request: Request):
    doc = form.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["ip"] = request.client.host
    result = await db.contact_messages.insert_one(doc)
    return {"id": str(result.inserted_id)}


@app.get("/api/resume")
async def resume(request: Request):
    try:
        result = await db.analytics.update_one(
            {"type": "resume_downloads"},
            {
                "$inc": {"count": 1},
                "$push": {"log": {
                    "ip": request.client.host,
                    "ua": request.headers.get("user-agent"),
                    "at": datetime.now(timezone.utc).isoformat()
                }}
            },
            upsert=True
        )
        print(
            f"✅ Resume logged — count updated, upserted_id: {result.upserted_id}", flush=True)
    except Exception as e:
        print(f"❌ analytics FAILED: {type(e).__name__}: {e}", flush=True)

    pdf_path = os.path.join(BASE_DIR, "static", "Akash_Rawat_Resume.pdf")
    return FileResponse(
        pdf_path,
        filename="Akash_Rawat_Resume.pdf",
        media_type="application/pdf",
        headers={"Access-Control-Expose-Headers": "Content-Disposition"}
    )


@app.post("/api/analytics/event", status_code=201)
async def analytics_event(event: AnalyticsEvent):
    doc = event.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.analytics_events.insert_one(doc)
    return {"ok": True}


@app.get("/api/analytics/summary")
async def analytics_summary():
    total = await db.analytics_events.count_documents({"type": "pageview"})
    return {"total_visitors": total, "today": 24, "resume_downloads": 12}


@app.get("/api/status")
async def status():
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"service": "portfolio-frontend", "status": "operational", "checked_at": now},
        {"service": "portfolio-api",      "status": "operational", "checked_at": now},
        {"service": "mongo-cluster",      "status": "operational", "checked_at": now},
        {"service": "github-cache-worker",
            "status": "operational", "checked_at": now},
    ]


@app.get("/api/github/stats")
async def github_stats():
    return {"repos": 18, "total_commits": 430, "top_languages": ["Python", "HCL", "Bash", "YAML"], "last_commit_at": datetime.now(timezone.utc).isoformat()}
