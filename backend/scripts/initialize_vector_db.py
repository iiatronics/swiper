# backend/scripts/initialize_vector_db.py
import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import faiss
import kagglehub
from sklearn.preprocessing import StandardScaler

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class Encoder(nn.Module):
    def __init__(self, num_dim, genre_vocab_size, genre_embed_dim=32, latent_dim=128):
        super().__init__()
        self.genre_embedding = nn.Embedding(genre_vocab_size, genre_embed_dim, padding_idx=0)
        genre_flat_dim = genre_embed_dim * 4
        self.net = nn.Sequential(
            nn.Linear(num_dim + genre_flat_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, latent_dim),
        )
    def forward(self, x_num, x_genres):
        g_emb = self.genre_embedding(x_genres)
        g_emb = g_emb.view(g_emb.size(0), -1)
        x = torch.cat([x_num, g_emb], dim=1)
        return self.net(x)
    
class InferenceDataset(Dataset):
    def __init__(self, X_num, X_genres):
        self.X_num = X_num
        self.X_genres = X_genres
    def __len__(self): return self.X_num.shape[0]
    def __getitem__(self, idx): return torch.from_numpy(self.X_num[idx]), torch.from_numpy(self.X_genres[idx])

if __name__ == '__main__':
    NEW_MODEL_PATH = "scripts\\model_v03.pt" 
    
    print(f"Завантаження оновленого чекпоінту {NEW_MODEL_PATH}...")
    checkpoint = torch.load(NEW_MODEL_PATH, weights_only=False, map_location=device)
    genre_encoders = checkpoint['genre_encoders']
    genre_vocab_size = checkpoint['genre_vocab_size']
    input_num_dim = 11

    encoder = Encoder(num_dim=input_num_dim, genre_vocab_size=genre_vocab_size).to(device)
    encoder.load_state_dict(checkpoint['encoder_state_dict'])
    encoder.eval()

    print("Підготовка датасету Spotify...")
    tonygordonjr_spotify_dataset_2023_path = kagglehub.dataset_download('tonygordonjr/spotify-dataset-2023')
    path = os.path.join(tonygordonjr_spotify_dataset_2023_path, 'spotify_data_12_20_2023.csv')
    songs = pd.read_csv(path, low_memory=False)

    audio_features = [
        'acousticness', 'danceability', 'energy', 'instrumentalness',
        'liveness', 'speechiness', 'valence', 'tempo', 'loudness', 'duration_ms'
    ]
    year_feature = 'release_year'
    numeric_features = audio_features + [year_feature]
    categorical_features = ['genre_0', 'genre_1', 'genre_2', 'genre_3'] # <-- ДОДАНО (було пропущено)

    df_all = songs.dropna(subset=['genre_0']).copy().reset_index(drop=True)

    # Точно повторюємо обробку з Colab для запобігання Data Mismatch
    for f in numeric_features:
        df_all[f] = df_all[f].fillna(df_all[f].median())
        df_all[f] = df_all[f].clip(df_all[f].quantile(0.01), df_all[f].quantile(0.99))

    scaler = StandardScaler()
    X_num_all = scaler.fit_transform(df_all[numeric_features]).astype('float32')

    X_genres_all = np.zeros((len(df_all), len(categorical_features)), dtype=np.int64)
    for i, col in enumerate(categorical_features):
        le = genre_encoders[col]
        vals = df_all[col].fillna('unknown').astype(str).values
        vals_cleaned = np.where(np.isin(vals, le.classes_), vals, le.classes_[0])
        X_genres_all[:, i] = le.transform(vals_cleaned) + 1

    inf_loader = DataLoader(InferenceDataset(X_num_all, X_genres_all), batch_size=4096, shuffle=False, num_workers=2)

    all_embeddings = []
    print("Embeddings generation...")
    with torch.no_grad():
        for x_num, x_genres in inf_loader:
            z = encoder(x_num.to(device), x_genres.to(device))
            all_embeddings.append(F.normalize(z, dim=1).cpu().numpy())

    all_embeddings = np.vstack(all_embeddings).astype('float32')

    print("Create FAISS index...")
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(all_embeddings.shape[1]))
    index.add_with_ids(all_embeddings, np.arange(len(all_embeddings)).astype('int64'))

    os.makedirs("data", exist_ok=True)
    faiss.write_index(index, "data/spotify_tracks.index")

    id_col = next((c for c in ['track_id', 'id', 'uri', 'spotify_id'] if c in df_all.columns), None)
    name_col = next((c for c in ['track_name', 'name', 'title'] if c in df_all.columns), None)
    artist_col = next((c for c in ['artists', 'artist', 'track_artist', 'artists_name'] if c in df_all.columns), None)
    
    metadata_df = pd.DataFrame({
        'faiss_id': np.arange(len(all_embeddings)),
        'spotify_id': df_all[id_col],
        'track_name': df_all[name_col],
        'artist': df_all[artist_col],
        'released_year': df_all[year_feature].astype(int), 
        'genre_0': df_all['genre_0'].fillna('unknown').astype(str),
        'genre_1': df_all['genre_1'].fillna('').astype(str),
        'genre_2': df_all['genre_2'].fillna('').astype(str),
        'genre_3': df_all['genre_3'].fillna('').astype(str)
    })

    metadata_df.to_csv("data/metadata_mapping.csv", index=False)
    print("Files successfully generated in the data/ folder")