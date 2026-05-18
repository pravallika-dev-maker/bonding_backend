from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1 import auth, users, moods, partners, separations, reflections
from .database import engine, Base
from .models import user, mood, invite_code, separation, notification, question_category, reflection_question, reflection_session, reflection_answer, reflection_comparison  # IMPORTANT: Import models to register them with Base


print("--- STARTING BOOTSTRAP ---")
# Create tables in the database
try:
    print("Connecting to DB to create tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ DB Tables synchronization complete!")
except Exception as e:
    print(f"❌ DB ERROR during startup: {e}")


print("Initializing FastAPI app...")
app = FastAPI(title="Bonded API", version="1.0.0")

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(moods.router, prefix="/api/v1")
app.include_router(partners.router, prefix="/api/v1")
app.include_router(separations.router, prefix="/api/v1")
app.include_router(reflections.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Bonded Backend is running 🚀", "docs": "/docs"}
