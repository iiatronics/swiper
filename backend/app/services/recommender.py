# backend/app/services/recommender.py
import numpy as np
import pandas as pd
import traceback
import ast
from fastapi import HTTPException
from app.services.vector_db import vector_db

# Our In-Memory "database" for users
# Structure: { user_id: { "vector": np.array, "history": set(track_ids) } }
USERS_DB = {}

def get_user_feed(user_id: str, count: int = 10) -> list:
    """
    Returns a deterministic, diversified track feed for a user.
    Guarantees no duplicate primary artists within a single delivery batch.
    """
    try:
        # 1. If the user is new or has an invalid profile, initialize with a random vector
        if user_id not in USERS_DB or USERS_DB[user_id].get("vector") is None:
            random_vec = np.random.randn(128).astype('float32')
            random_vec /= np.linalg.norm(random_vec)
            USERS_DB[user_id] = {
                "vector": random_vec,
                "history": set()
            }
            
        user_profile = USERS_DB[user_id]
        user_vector = user_profile["vector"]
        user_history = user_profile["history"]

        # Ensure correct float32 shape for FAISS C++ layer
        user_tensor = np.array(user_vector, dtype=np.float32).reshape(1, -1)

        # 2. Request a large pool of candidates from FAISS with a buffer
        D, I = vector_db.index.search(user_tensor, 150)  # Increased buffer to 150 for deeper filtering
        candidate_ids = I[0].tolist()

        feed_cards = []
        primary_artist_counts = {}
        MAX_PER_ARTIST = 1  # Strict constraint: maximum 1 track per primary artist in a single batch

        # 3. Deterministic selection and diversification
        for track_id in candidate_ids:
            if track_id == -1:
                continue
                
            if track_id in user_history:
                continue
                
            try:
                metadata = vector_db.metadata.iloc[track_id]
            except IndexError:
                continue
                
            # Safely extract and normalize track metadata
            raw_artist_str = metadata.get('artist')
            artist_str = str(raw_artist_str) if pd.notna(raw_artist_str) else "Unknown Artist"
            
            raw_name = metadata.get('track_name')
            track_name = str(raw_name) if pd.notna(raw_name) else "Unknown Track"
            
            raw_spotify_id = metadata.get('spotify_id')
            spotify_id = str(raw_spotify_id) if pd.notna(raw_spotify_id) else ""
            
            # DATA CLEANING: Extract the primary (first) artist from the stringified list
            # e.g., converts "['Lana Del Rey', 'The Weeknd']" -> "Lana Del Rey"
            primary_artist = "Unknown Artist"
            try:
                if artist_str.startswith('[') and artist_str.endswith(']'):
                    artists_list = ast.literal_eval(artist_str)
                    if artists_list and len(artists_list) > 0:
                        primary_artist = str(artists_list[0]).strip()
                else:
                    primary_artist = artist_str.split(',')[0].replace("'", "").replace("[", "").strip()
            except Exception:
                # Basic string fallback trimming if literal evaluation fails
                primary_artist = artist_str.replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(",")[0].strip()

            # Deduplication check using the isolated Primary Artist name
            current_artist_count = primary_artist_counts.get(primary_artist, 0)
            
            if current_artist_count < MAX_PER_ARTIST:
                feed_cards.append({
                    "track_id": int(metadata['faiss_id']),
                    "spotify_id": spotify_id,
                    "name": track_name,
                    "artist": artist_str # We still return the full feature list to the frontend
                })
                # Lock this primary artist for the rest of the batch
                primary_artist_counts[primary_artist] = current_artist_count + 1
                
            if len(feed_cards) == count:
                break

        return feed_cards

    except Exception as e:
        print("\n" + "="*50 + " BACKEND ERROR TRACEBACK " + "="*50)
        print(traceback.format_exc())
        print("="*125 + "\n")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal error in recommender engine: [{type(e).__name__}] -> {str(e)}"
        )


def update_user_profile(user_id: str, track_id: int, direction: str, alpha: float = 0.8):
    """
    Updates the user's interest vector using the exponential smoothing formula.
    """
    if user_id not in USERS_DB:
        return
        
    user_profile = USERS_DB[user_id]
    user_profile["history"].add(track_id)
    
    if direction == "like":
        try:
            track_vector = vector_db.reconstruct_vector(track_id)
            old_vector = user_profile["vector"]
            new_vector = alpha * old_vector + (1 - alpha) * track_vector
            new_vector /= np.linalg.norm(new_vector)
            user_profile["vector"] = new_vector.astype('float32')
        except Exception:
            pass