# main.py
import os
import faiss
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Music Tinder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FAISS_INDEX = None
METADATA_DF = None
LATENT_DIM = 128
ALPHA = 0.8 

# structure: { user_id: { "vector": np.array, "history": set(faiss_ids) } }
USERS_DB = {}

@app.on_event("startup")
def load_resources():
    global FAISS_INDEX, METADATA_DF
    index_path = "data/spotify_tracks.index"
    meta_path = "data/metadata_mapping.csv"
    
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise RuntimeError("run database init script first")
        
    print("Download FAISS index...")
    FAISS_INDEX = faiss.read_index(index_path)
    
    print("Download metadata...")
    METADATA_DF = pd.read_csv(meta_path)
    print("Backend is ready!")


# Pydantic schemes
class RegisterRequest(BaseModel):
    user_id: str
    seed_track_ids: list[int]  # List of faiss_id tracks that the user selected at the start

class SwipeRequest(BaseModel):
    user_id: str
    track_id: int              # faiss_id of track
    direction: str             # "like" або "dislike"


# end point

@app.post("/api/v1/users/register")
def register_user(req: RegisterRequest):
    """Creates a user profile and initializes their interest vector"""
    if req.user_id in USERS_DB:
        return {"status": "already_registered", "message": "Користувач вже існує"}
    
    # collect vectors of selected tracks to form the initial profile
    vectors = []
    for tid in req.seed_track_ids:
        try:
            # extract the original vector from the FAISS index
            vec = FAISS_INDEX.reconstruct(int(tid))
            vectors.append(vec)
        except Exception:
            continue
            
    if not vectors:
        # if nothing is found, initialize with a random normalized vector
        user_vector = np.random.randn(LATENT_DIM).astype('float32')
    else:
        # averaging the vectors of the starting tracks
        user_vector = np.mean(vectors, axis=0).astype('float32')
    
    # normalize for cosine similarity
    user_vector /= np.linalg.norm(user_vector) + 1e-8
    
    # store in our In-Memory database
    USERS_DB[req.user_id] = {
        "vector": user_vector,
        "history": set(req.seed_track_ids) # immediately hide the starting tracks from the output
    }
    return {"status": "success", "user_id": req.user_id}


@app.get("/api/v1/feed")
def get_feed(user_id: str, count: int = 10):
    """Returns a pack of new track cards for swipes"""
    if user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")
        
    user_data = USERS_DB[user_id]
    user_vector = user_data["vector"].reshape(1, -1)
    history = user_data["history"]
    
    scores, suggested_ids = FAISS_INDEX.search(user_vector, k=150)
    suggested_ids = suggested_ids[0].tolist()
    
    # filter out tracks that the user has already swiped
    fresh_ids = [tid for tid in suggested_ids if tid not in history]
    
    # take the final pack (for example, 10 tracks)
    final_batch_ids = fresh_ids[:count]
    
    # extract the text metadata for these IDs from our DataFrame
    cards = []
    tracks_meta = METADATA_DF[METADATA_DF['faiss_id'].isin(final_batch_ids)]
    
    for _, row in tracks_meta.iterrows():
        cards.append({
            "track_id": int(row['faiss_id']),
            "spotify_id": row['spotify_id'],
            "name": row['track_name'],
            "artist": row['artist']
        })
        
    return {"user_id": user_id, "cards": cards}


@app.post("/api/v1/swipe")
def process_swipe(req: SwipeRequest):
    """Processes swipes: adds to history and adapts interest vector in case of like"""
    if req.user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="Юзера не знайдено")
        
    user_data = USERS_DB[req.user_id]
    
    # 1. Repeat protection: add the track to the blacklist (history)
    user_data["history"].add(req.track_id)
    
    # 2. If it's a LIKE, we smoothly shift the user's vector towards this track.
    if req.direction == "like":
        try:
            track_vector = FAISS_INDEX.reconstruct(int(req.track_id))
            old_user_vector = user_data["vector"]
            
            # Формула ковзного середнього
            new_vector = ALPHA * old_user_vector + (1 - ALPHA) * track_vector
            # Повторна нормалізація на одиничну сферу
            new_vector /= np.linalg.norm(new_vector) + 1e-8
            
            user_data["vector"] = new_vector
            status = "vector_updated"
        except Exception as e:
            status = f"error_reconstructing_vector: {str(e)}"
    else:
        status = "disliked_tracked_ignored"
        
    return {"status": "success", "action": status, "history_size": len(user_data["history"])}