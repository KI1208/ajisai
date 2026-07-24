from fastapi import FastAPI
from contextlib import asynccontextmanager

from database import engine, Base
from api import webhook, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all database tables on startup (especially useful for local sqlite)
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="ajisai LINE Chatbot API",
    description="Backend for the LINE-based personal diary and AI weekly report app.",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(webhook.router)
app.include_router(scheduler.router)

@app.get("/")
def read_root():
    return {"message": "ajisai API is running smoothly!"}
