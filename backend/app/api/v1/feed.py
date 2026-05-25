from fastapi import APIRouter, HTTPException
from app.schemas.feed import SwipeRequest
from app.services.recommender import get_user_feed, update_user_profile

router = APIRouter(prefix="/v1")

@router.get("/feed")
def feed(user_id: str, count: int = 10):
    try:
        tracks_df = get_user_feed(user_id, count)
        cards = []
        for _, row in tracks_df.iterrows():
            cards.append({
                "track_id": int(row['faiss_id']),
                "spotify_id": row['spotify_id'],
                "name": row['track_name'],
                "artist": row['artist']
            })
        return {"user_id": user_id, "cards": cards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/swipe")
def swipe(req: SwipeRequest):
    if req.direction not in ["like", "dislike"]:
        raise HTTPException(status_code=400, detail="Direction must be 'like' or 'dislike'")
    update_user_profile(req.user_id, req.track_id, req.direction)
    return {"status": "success"}