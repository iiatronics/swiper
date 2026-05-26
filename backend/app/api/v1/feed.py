from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.recommender import get_user_feed, update_user_profile

# Using empty APIRouter() to fix the double "/v1/v1" prefix issue in URLs
router = APIRouter()

class SwipeRequest(BaseModel):
    user_id: str
    track_id: int
    direction: str

@router.get("/feed")
def read_feed(user_id: str, count: int = 10):
    """
    Main feed endpoint. Fetches a list of recommended tracks from the recommender service.
    """
    # get_user_feed returns a native Python list, we just pass it directly to the response
    cards = get_user_feed(user_id, count=count)
    return {"user_id": user_id, "cards": cards}

@router.post("/swipe")
def swipe_track(request: SwipeRequest):
    """
    Handles user swipes (likes/dislikes) and updates their geometric profile.
    """
    update_user_profile(request.user_id, request.track_id, request.direction)
    return {"status": "success"}

@router.get("/debug/search-track")
def debug_search_track(query: str):
    """
    Allows searching for a track_id or artist name using a text query.
    """
    from app.services.vector_db import vector_db
    
    df = vector_db.metadata
    mask = df['track_name'].str.contains(query, case=False, na=False) | \
           df['artist'].str.contains(query, case=False, na=False)
           
    results = df[mask].head(20)
    
    cards = []
    # .iterrows() belongs here because 'results' is a valid Pandas DataFrame
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
    Forces a user's profile vector to match a specific track's vector for testing.
    """
    from app.services.recommender import USERS_DB
    from app.services.vector_db import vector_db
    
    try:
        track_vector = vector_db.reconstruct_vector(track_id)
        USERS_DB[user_id] = {
            "vector": track_vector,
            "history": {track_id}
        }
        return {
            "status": "success", 
            "message": f"Смак користувача {user_id} успішно синхронізовано з треком ID {track_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading track vector: {str(e)}")
    
    