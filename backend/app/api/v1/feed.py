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

@router.get("/debug/search-track")
def debug_search_track(query: str):
    """
    Allows you to find the faiss_id of a song or artist by text query.
    For example: query='Eminem' or query='In the end'
    """
    from app.services.vector_db import vector_db
    
    df = vector_db.metadata
    
    mask = df['track_name'].str.contains(query, case=False, na=False) | \
           df['artist'].str.contains(query, case=False, na=False)
           
    results = df[mask].head(20)
    
    cards = []
    for _, row in results.iterrows():
        cards.append({
            "track_id": int(row['faiss_id']),
            "spotify_id": row['spotify_id'],
            "name": row['track_name'],
            "artist": row['artist']
        })
    return {"query": query, "found_count": len(cards), "results": cards}


@router.post("/debug/force-user-taste")
def debug_force_user_taste(user_id: str, track_id: int):
    """
    Forcibly overwrites the user vector with the vector of a specific track.
    This allows you to check what the model thinks is 'closest' to this song.
    """
    from app.services.recommender import USERS_DB
    from app.services.vector_db import vector_db
    
    try:
        track_vector = vector_db.reconstruct_vector(track_id)
        
        USERS_DB[user_id] = {
            "vector": track_vector,
            "history": {track_id} # Одразу ховаємо цей трек, щоб бачити тільки схожі
        }
        return {
            "status": "success", 
            "message": f"Смак користувача {user_id} успішно синхронізовано з треком ID {track_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування вектора треку: {str(e)}")