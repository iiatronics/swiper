from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.feed import router as feed_router

app = FastAPI(title="Swiper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# add endpoints
app.include_router(feed_router, prefix="/api/v1")