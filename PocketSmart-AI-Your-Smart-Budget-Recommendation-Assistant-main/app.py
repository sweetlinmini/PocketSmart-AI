import os
import io
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from PIL import Image
from dotenv import load_dotenv

# Load .env before using environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai = None
if GEMINI_API_KEY:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ GEMINI_API_KEY not configured. AI features will be disabled until a valid key is added to .env")

# FastAPI app initialization
app = FastAPI(title="PocketSmart: AI Budget Planner")

SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
templates.env.globals["app_name"] = "PocketSmart"
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Single import from state at the top
from state import recommendation_history

# Import routers
from routers import home, party, jewelry, auth

app.include_router(auth.router)
app.include_router(home.router)
app.include_router(party.router)
app.include_router(jewelry.router)

# ── Startup Event ──────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("✅ PocketSmart AI starting up...")
    print("✅ Gemini API key loaded")
    print("✅ All routers registered")
    print("✅ Server ready!")

@app.get("/startup")
async def startup_status():
    return {
        "status": "running",
        "message": "PocketSmart AI is operational",
        "timestamp": datetime.utcnow().isoformat()
    }

# ── Root → Landing Page ────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/login")

# ── Login & Register pages ─────────────────────────────────
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"request": request})

# ── Dashboard & History pages ──────────────────────────────
@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse(request, "history.html", {"request": request})

# ── API History ────────────────────────────────────────────
@app.get("/api/history")
async def get_history_api():
    return {
        "total": len(recommendation_history),
        "history": recommendation_history
    }

@app.delete("/api/history")
async def clear_history_api():
    recommendation_history.clear()
    return {"message": "History cleared successfully"}

# ── Recommendation Details ─────────────────────────────────
@app.post("/recommendations-details")
async def recommendations_details(request: Request):
    if genai is None:
        return {"detail": "AI recommendations are unavailable because GEMINI_API_KEY is not configured. Add it to your .env file to enable Gemini."}

    body = await request.json()
    category = body.get("category", "home")
    budget = body.get("budget", 0)
    preferences = body.get("preferences", {})

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    You are PocketSmart AI, a budget recommendation expert.
    Category: {category}
    Budget: ₹{budget}
    Preferences: {preferences}

    Provide detailed product recommendations with:
    - Product name
    - Price in INR
    - Platform (Amazon/Flipkart/IKEA/Swiggy/Zomato)
    - Direct search URL
    - Why it fits the budget and preference

    Be specific and practical. Stay within budget.
    """

    response = model.generate_content(prompt)

    # Save to history
    history_entry = {
        "id": str(uuid.uuid4()),
        "category": category,
        "budget": budget,
        "preferences": preferences,
        "result": response.text,
        "timestamp": datetime.utcnow().isoformat()
    }
    recommendation_history.append(history_entry)

    return {"recommendations": response.text, "id": history_entry["id"]}


# ── Main Entry Point ───────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)