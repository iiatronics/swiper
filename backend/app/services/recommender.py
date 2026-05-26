import numpy as np
from app.config import ALPHA, LATENT_DIM
from app.services.vector_db import vector_db

# temp In-Memory base of users

USERS_DB = {}

def get_user_feed(user_id: str, count: int = 10):
    if user_id not in USERS_DB:
       
        vec = np.random.randn(LATENT_DIM).astype('float32')
        vec /= np.linalg.norm(vec) + 1e-8
        USERS_DB[user_id] = {"vector": vec, "history": set()}
        
    user_data = USERS_DB[user_id]
    user_vec = user_data["vector"].reshape(1, -1)
    
    # search for candidates in FAISS
    suggested_ids = vector_db.search_neighbors(user_vec, k=150)
    
    # filter swipes history
    fresh_ids = [tid for tid in suggested_ids if tid not in user_data["history"]][:count]
    
    # return clean recommendations
    return vector_db.get_tracks_metadata(fresh_ids)

def update_user_profile(user_id: str, track_id: int, direction: str):
    if user_id not in USERS_DB:
        return
    
    USERS_DB[user_id]["history"].add(track_id)
    
    if direction == "like":
        track_vec = vector_db.reconstruct_vector(track_id)
        old_user_vec = USERS_DB[user_id]["vector"]
        
        # formula of pref adapts
        new_vec = ALPHA * old_user_vec + (1 - ALPHA) * track_vec
        new_vec /= np.linalg.norm(new_vec) + 1e-8
        USERS_DB[user_id]["vector"] = new_vec