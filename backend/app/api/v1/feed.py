from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.recommender import get_user_feed, update_user_profile
from app.services.vector_db import vector_db
import pandas as pd
import numpy as np

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

@router.get("/debug/test-embedding-orthogonality")
def debug_test_embedding_orthogonality(group_idx: int = 0):
    """
    TRUE GENRE ORTHOGONALITY TEST
    Allows skipping biased top groups (like identical classical albums) using 'group_idx'.
    Finds a dense cross-artist genre cluster and evaluates the exact mathematical divergence.
    """
    df = vector_db.metadata.copy()
    genre_cols = ['genre_0', 'genre_1', 'genre_2', 'genre_3']
    
    if not all(col in df.columns for col in genre_cols):
        raise HTTPException(
            status_code=400, 
            detail="Metadata missing genre columns. Please update initialize_vector_db.py and rerun it."
        )
        
    group_sizes = df.groupby(genre_cols).size().reset_index(name='count')
    dense_groups = group_sizes[group_sizes['count'] >= 20].sort_values(by='count', ascending=False)
    
    if dense_groups.empty:
        raise HTTPException(status_code=404, detail="No dense genre groups found with >= 20 tracks.")
        
    if group_idx >= len(dense_groups):
        raise HTTPException(
            status_code=400, 
            detail=f"group_idx {group_idx} is out of bounds. Max available index is {len(dense_groups) - 1}"
        )
        
    # Pick the genre combination based on the user-supplied index
    target_genre_row = dense_groups.iloc[group_idx]
    mask = True
    for col in genre_cols:
        mask = mask & (df[col] == target_genre_row[col])
        
    sub_df = df[mask].head(60)  # Scan up to 60 tracks in this specific genre box
    faiss_ids = sub_df['faiss_id'].values
    
    vectors = []
    valid_indices = []
    for i, f_id in enumerate(faiss_ids):
        try:
            vec = vector_db.index.reconstruct(int(f_id))
            vec = vec / np.linalg.norm(vec)
            vectors.append(vec)
            valid_indices.append(i)
        except Exception:
            continue
            
    num_valid = len(vectors)
    if num_valid < 2:
        raise HTTPException(status_code=500, detail="Failed to reconstruct enough vectors from FAISS.")
        
    min_sim = 2.0
    max_sim = -2.0
    worst_pair = (0, 0)
    best_pair = (0, 0)
    
    for i in range(num_valid):
        for j in range(i + 1, num_valid):
            sim = float(np.dot(vectors[i], vectors[j]))
            
            if sim < min_sim:
                min_sim = sim
                worst_pair = (i, j)
            if sim > max_sim:
                max_sim = sim
                best_pair = (i, j)
                
    meta_least_1 = sub_df.iloc[valid_indices[worst_pair[0]]]
    meta_least_2 = sub_df.iloc[valid_indices[worst_pair[1]]]
    
    meta_most_1 = sub_df.iloc[valid_indices[best_pair[0]]]
    meta_most_2 = sub_df.iloc[valid_indices[best_pair[1]]]
    
    clean_genres = [str(target_genre_row[col]) for col in genre_cols if pd.notna(target_genre_row[col]) and target_genre_row[col] != ""]
    
    return {
        "status": "success",
        "current_group_index": group_idx,
        "exact_shared_genres": clean_genres,
        "tracks_evaluated_in_this_box": num_valid,
        "most_orthogonal_pair_inside_this_genre": {
            "cosine_similarity": round(min_sim, 4),
            "track_1": {"name": str(meta_least_1['track_name']), "artist": str(meta_least_1['artist']), "faiss_id": int(meta_least_1['faiss_id'])},
            "track_2": {"name": str(meta_least_2['track_name']), "artist": str(meta_least_2['artist']), "faiss_id": int(meta_least_2['faiss_id'])}
        },
        "most_similar_pair_inside_this_genre": {
            "cosine_similarity": round(max_sim, 4),
            "track_1": {"name": str(meta_most_1['track_name']), "artist": str(meta_most_1['artist']), "faiss_id": int(meta_most_1['faiss_id'])},
            "track_2": {"name": str(meta_most_2['track_name']), "artist": str(meta_most_2['artist']), "faiss_id": int(meta_most_2['faiss_id'])}
        }
    }