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

print("Завантаження моделі...")
checkpoint = torch.load("model_v01.pt", map_location=device)
global_le = checkpoint['global_genre_encoder']
genre_vocab_size = checkpoint['genre_vocab_size']

encoder = Encoder(num_dim=10, genre_vocab_size=genre_vocab_size).to(device)
encoder.load_state_dict(checkpoint['encoder_state_dict'])
encoder.eval()

print("Підготовка датасету Spotify...")
tonygordonjr_spotify_dataset_2023_path = kagglehub.dataset_download('tonygordonjr/spotify-dataset-2023')
path = os.path.join(tonygordonjr_spotify_dataset_2023_path, 'spotify_data_12_20_2023.csv')
songs = pd.read_csv(path, low_memory=False)

numeric_features = ['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'speechiness', 'valence', 'tempo', 'loudness', 'duration_ms']
categorical_features = ['genre_0', 'genre_1', 'genre_2', 'genre_3']

df_all = songs.dropna(subset=['genre_0']).copy().reset_index(drop=True)

for f in numeric_features:
    df_all[f] = df_all[f].fillna(df_all[f].median())
    df_all[f] = df_all[f].clip(df_all[f].quantile(0.01), df_all[f].quantile(0.99))

scaler = StandardScaler()
X_num_all = scaler.fit_transform(df_all[numeric_features]).astype('float32')

X_genres_all = np.zeros((len(df_all), len(categorical_features)), dtype=np.int64)
for i, col in enumerate(categorical_features):
    vals = df_all[col].fillna('unknown').astype(str).values
    vals_cleaned = np.where(np.isin(vals, global_le.classes_), vals, 'unknown')
    X_genres_all[:, i] = global_le.transform(vals_cleaned) + 1

class InferenceDataset(Dataset):
    def __init__(self, X_num, X_genres):
        self.X_num = X_num
        self.X_genres = X_genres
    def __len__(self): return self.X_num.shape[0]
    def __getitem__(self, idx): return torch.from_numpy(self.X_num[idx]), torch.from_numpy(self.X_genres[idx])

inf_loader = DataLoader(InferenceDataset(X_num_all, X_genres_all), batch_size=4096, shuffle=False, num_workers=2)

all_embeddings = []
print("Embeddings generation...")
with torch.no_grad():
    for x_num, x_genres in inf_loader:
        z = encoder(x_num.to(device), x_genres.to(device))
        all_embeddings.append(F.normalize(z, dim=1).cpu().numpy())

all_embeddings = np.vstack(all_embeddings).astype('float32')

print("Create FAISS index...")
index = faiss.IndexIDMap(faiss.IndexFlatIP(all_embeddings.shape[1]))
index.add_with_ids(all_embeddings, np.arange(len(all_embeddings)).astype('int64'))

os.makedirs("data", exist_ok=True)
faiss.write_index(index, "data/spotify_tracks.index")

metadata_df = pd.DataFrame({
    'faiss_id': np.arange(len(all_embeddings)),
    'spotify_id': df_all['id'],
    'track_name': df_all['name'],
    'artist': df_all['artists']
})
metadata_df.to_csv("data/metadata_mapping.csv", index=False)
print("Files successfully generated in the data/ folder")