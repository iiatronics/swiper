import numpy as np
from app.config import ALPHA, LATENT_DIM
from app.services.vector_db import vector_db

# Тимчасова In-Memory база користувачів
USERS_DB = {}

def get_user_feed(user_id: str, count: int = 10):
    if user_id not in USERS_DB:
        # Холодний старт: якщо юзера немає, створюємо йому дефолтний нормалізований вектор
        vec = np.random.randn(LATENT_DIM).astype('float32')
        vec /= np.linalg.norm(vec) + 1e-8
        USERS_DB[user_id] = {"vector": vec, "history": set()}
        
    user_data = USERS_DB[user_id]
    user_vec = user_data["vector"].reshape(1, -1)
    
    # Шукаємо кандидатів у FAISS
    suggested_ids = vector_db.search_neighbors(user_vec, k=150)
    
    # Фільтруємо історію свайпів
    fresh_ids = [tid for tid in suggested_ids if tid not in user_data["history"]][:count]
    
    # Повертаємо датафрейм із чистими картками
    return vector_db.get_tracks_metadata(fresh_ids)

def update_user_profile(user_id: str, track_id: int, direction: str):
    if user_id not in USERS_DB:
        return
    
    USERS_DB[user_id]["history"].add(track_id)
    
    if direction == "like":
        track_vec = vector_db.reconstruct_vector(track_id)
        old_user_vec = USERS_DB[user_id]["vector"]
        
        # Формула адаптації смаків
        new_vec = ALPHA * old_user_vec + (1 - ALPHA) * track_vec
        new_vec /= np.linalg.norm(new_vec) + 1e-8
        USERS_DB[user_id]["vector"] = new_vec