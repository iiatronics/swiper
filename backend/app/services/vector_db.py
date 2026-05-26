import faiss
import pandas as pd
from app.config import INDEX_PATH, METADATA_PATH

class VectorDBService:
    def __init__(self):
        self.index = faiss.read_index(INDEX_PATH)
        self.metadata = pd.read_csv(METADATA_PATH)

    def search_neighbors(self, user_vector, k=150):
        scores, ids = self.index.search(user_vector, k)
        return ids[0].tolist()

    def get_tracks_metadata(self, track_ids):

        return self.metadata[self.metadata['faiss_id'].isin(track_ids)]

    def reconstruct_vector(self, track_id):
        return self.index.reconstruct(int(track_id))

vector_db = VectorDBService()