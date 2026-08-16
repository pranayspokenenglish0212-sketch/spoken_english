from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Pranay Sir's Spoken English API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# =========================
# Models
# =========================
class Enquiry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    course: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EnquiryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=20)
    course: Optional[str] = Field(default=None, max_length=80)
    message: Optional[str] = Field(default=None, max_length=1000)


# --- Feedback Models ---
class Feedback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_name: str
    rating: int
    comment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FeedbackCreate(BaseModel):
    student_name: str = Field(min_length=2, max_length=100)
    rating: int = Field(ge=1, le=5)  # Restricts rating strictly between 1 and 5
    comment: str = Field(min_length=5, max_length=1000)


# =========================
# Routes
# =========================
@api_router.get("/")
async def root():
    return {"message": "Pranay Sir's Spoken English API is live"}


# --- Enquiry Routes ---
@api_router.post("/enquiries", response_model=Enquiry, status_code=201)
async def create_enquiry(payload: EnquiryCreate):
    enquiry = Enquiry(**payload.model_dump())
    doc = enquiry.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.enquiries.insert_one(doc)
    return enquiry


@api_router.get("/enquiries", response_model=List[Enquiry])
async def list_enquiries(limit: int = 100):
    cursor = db.enquiries.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    for item in items:
        if isinstance(item.get('created_at'), str):
            try:
                item['created_at'] = datetime.fromisoformat(item['created_at'])
            except ValueError:
                item['created_at'] = datetime.now(timezone.utc)
    return items


# --- Feedback Routes ---
@api_router.post("/feedback", response_model=Feedback, status_code=201)
async def create_feedback(payload: FeedbackCreate):
    feedback = Feedback(**payload.model_dump())
    doc = feedback.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.feedback.insert_one(doc)
    return feedback


@api_router.get("/feedback", response_model=List[Feedback])
async def list_feedback(limit: int = 100):
    cursor = db.feedback.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    for item in items:
        if isinstance(item.get('created_at'), str):
            try:
                item['created_at'] = datetime.fromisoformat(item['created_at'])
            except ValueError:
                item['created_at'] = datetime.now(timezone.utc)
    return items


# --- Stats Route ---
@api_router.get("/stats")
async def stats():
    """Public-facing stats for the landing page."""
    total = await db.enquiries.count_documents({})
    return {
        "google_rating": 5.0,
        "google_reviews": 211,
        "students_trained": 5000,
        "years_experience": 12,
        "enquiries_received": total,
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()