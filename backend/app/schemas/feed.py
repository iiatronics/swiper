from pydantic import BaseModel

class RegisterRequest(BaseModel):
    user_id: str
    seed_track_ids: list[int]  # List of faiss_id tracks that the user selected at the start

class SwipeRequest(BaseModel):
    user_id: str
    track_id: int              # faiss_id of track
    direction: str             # "like" або "dislike"
