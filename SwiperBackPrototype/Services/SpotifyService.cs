using System.Net.Http.Headers;
using System.Text.Json;

namespace SwiperBack.Services;

public class SpotifyService
{
    private const string Base = "https://api.spotify.com/v1";

    private static async Task<JsonElement> Get(string token, string url)
    {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        Console.WriteLine($"→ GET {url}");
        var resp = await http.GetAsync(url);
        var body = await resp.Content.ReadAsStringAsync();
        if (!resp.IsSuccessStatusCode)
            throw new Exception($"{(int)resp.StatusCode} {resp.ReasonPhrase}: {body}");
        return JsonSerializer.Deserialize<JsonElement>(body);
    }

    private static async Task<JsonElement> Post(string token, string url, object payload)
    {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        var content = new StringContent(
            JsonSerializer.Serialize(payload),
            System.Text.Encoding.UTF8,
            "application/json");
        var resp = await http.PostAsync(url, content);
        var body = await resp.Content.ReadAsStringAsync();
        if (!resp.IsSuccessStatusCode)
            throw new Exception($"{(int)resp.StatusCode} {resp.ReasonPhrase}: {body}");
        return JsonSerializer.Deserialize<JsonElement>(body);
    }

    // ── "Радіо" через Artist Albums ───────────────────────────────────────────
    // related-artists заблокований у Dev mode з 2024.
    // Замість нього: беремо артиста seed треку → його альбоми → треки з них.
    // Плюс шукаємо схожих через search по імені артиста.
    public async Task<List<JsonElement>> GetRadioTracksAsync(string token, string seedTrackId)
    {
        var result = new List<JsonElement>();

        try
        {
            // Крок 1: отримуємо seed трек
            var track = await Get(token, $"{Base}/tracks/{seedTrackId}");
            var artistId   = track.GetProperty("artists")[0].GetProperty("id").GetString()!;
            var artistName = track.GetProperty("artists")[0].GetProperty("name").GetString()!;
            Console.WriteLine($"🎵 Seed: {track.GetProperty("name").GetString()} — {artistName}");

            // Крок 2: альбоми артиста → треки
            var albumsData = await Get(token,
                $"{Base}/artists/{artistId}/albums?include_groups=album,single&limit=10");

            var albums = albumsData.GetProperty("items").EnumerateArray().ToList();
            Console.WriteLine($"💿 Альбомів: {albums.Count}");

            foreach (var album in albums.Take(4))
            {
                var albumId = album.GetProperty("id").GetString()!;
                try
                {
                    var albumTracks = await Get(token, $"{Base}/albums/{albumId}/tracks?limit=5");
                    // tracks з альбому не мають повної інформації — треба дозавантажити
                    var trackIds = albumTracks.GetProperty("items")
                        .EnumerateArray()
                        .Select(t => t.GetProperty("id").GetString()!)
                        .ToList();

                    if (trackIds.Count > 0)
                    {
                        var ids = string.Join(",", trackIds);
                        var fullTracks = await Get(token, $"{Base}/tracks?ids={ids}");
                        result.AddRange(fullTracks.GetProperty("tracks").EnumerateArray());
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"  ✗ album {albumId}: {ex.Message}");
                }
            }

            // Крок 3: search по імені артиста — знаходить схожих виконавців
            var q = Uri.EscapeDataString(artistName);
            try
            {
                var searchData = await Get(token, $"{Base}/search?q={q}&type=track");
                var searchTracks = searchData.GetProperty("tracks")
                    .GetProperty("items").EnumerateArray();
                result.AddRange(searchTracks);
                Console.WriteLine($"🔍 Search додав треки для '{artistName}'");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"  ✗ search: {ex.Message}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ GetRadioTracks: {ex.Message}");
        }

        result = result.OrderBy(_ => Random.Shared.Next()).ToList();
        Console.WriteLine($"✅ Радіо зібрало {result.Count} треків");
        return result;
    }

    // ── Search fallback ───────────────────────────────────────────────────────
    public async Task<List<JsonElement>> SearchTracksAsync(string token, string query)
    {
        var q = Uri.EscapeDataString(query);
        var attempts = new[]
        {
            $"{Base}/search?q={q}&type=track",
            $"{Base}/search?q={q}&type=track&market=US",
            $"{Base}/search?q=pop&type=track&market=US",
            $"{Base}/search?q=pop&type=track",
        };

        foreach (var url in attempts)
        {
            try
            {
                var data  = await Get(token, url);
                var items = data.GetProperty("tracks").GetProperty("items")
                               .EnumerateArray().ToList();
                Console.WriteLine($"✓ Search '{query}' → {items.Count} треків");
                return items;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"✗ search attempt: {ex.Message}");
            }
        }
        return [];
    }

    // ── Топ треки користувача ─────────────────────────────────────────────────
    public async Task<List<JsonElement>> GetUserTopTracksAsync(string token, int limit = 5)
    {
        try
        {
            var data = await Get(token,
                $"{Base}/me/top/tracks?limit={limit}&time_range=medium_term");
            return data.GetProperty("items").EnumerateArray().ToList();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"⚠ top/tracks: {ex.Message}");
            return [];
        }
    }

    // ── Профіль ───────────────────────────────────────────────────────────────
    public async Task<JsonElement> GetProfileAsync(string token)
        => await Get(token, $"{Base}/me");

    // ── Плейлист: створити ────────────────────────────────────────────────────
    public async Task<string> CreatePlaylistAsync(string token, string userId, string name)
    {
        var data = await Post(token, $"{Base}/users/{userId}/playlists", new
        {
            name,
            description = "Created by Swiper 🎵",
            @public = false
        });
        return data.GetProperty("id").GetString()!;
    }

    // ── Плейлист: додати треки ────────────────────────────────────────────────
    public async Task AddToPlaylistAsync(string token, string playlistId, List<string> ids)
    {
        if (ids.Count == 0) return;
        var uris = ids.Select(id => $"spotify:track:{id}").ToList();
        await Post(token, $"{Base}/playlists/{playlistId}/tracks", new { uris });
    }

    // ── Плейлист: отримати ID треків ──────────────────────────────────────────
    public async Task<HashSet<string>> GetPlaylistTrackIdsAsync(string token, string playlistId)
    {
        try
        {
            var data = await Get(token,
                $"{Base}/playlists/{playlistId}/tracks?fields=items(track(id))&limit=100");
            return data.GetProperty("items")
                       .EnumerateArray()
                       .Where(i => i.TryGetProperty("track", out var t)
                                   && t.ValueKind != JsonValueKind.Null)
                       .Select(i => i.GetProperty("track").GetProperty("id").GetString()!)
                       .ToHashSet();
        }
        catch { return []; }
    }
}