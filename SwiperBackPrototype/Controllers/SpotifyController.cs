using Microsoft.AspNetCore.Mvc;
using SwiperBack.Models;
using SwiperBack.Services;
using System.Text.Json;

namespace SwiperBack.Controllers;

[ApiController]
[Route("api/spotify")]
public class SpotifyController(SpotifyService spotify, StorageService storage) : ControllerBase
{
    private string Token =>
        Request.Headers.Authorization.ToString().Replace("Bearer ", "").Trim();

    // ── GET /api/spotify/recommendations ─────────────────────────────────────
    [HttpGet("recommendations")]
    public async Task<IActionResult> GetRecommendations()
    {
        if (string.IsNullOrEmpty(Token)) return Unauthorized();
        try
        {
            var swiped = storage.GetAllSwipedIds();
            var liked  = storage.GetLikedIds();

            List<JsonElement> rawTracks = [];

            if (liked.Count > 0)
            {
                // ── РЕЖИМ РАДІО ──────────────────────────────────────────────
                // Беремо рандомний лайкнутий трек як seed для радіо
                var seedId = liked[Random.Shared.Next(liked.Count)];
                Console.WriteLine($"📻 Радіо на основі: {seedId}");
                rawTracks = await spotify.GetRadioTracksAsync(Token, seedId);
            }
            else
            {
                // ── ХОЛОДНИЙ СТАРТ ───────────────────────────────────────────
                // Беремо топ треки юзера → радіо на основі одного з них
                var topTracks = await spotify.GetUserTopTracksAsync(Token, 15);

                if (topTracks.Count > 0)
                {
                    var seedTrack = topTracks[Random.Shared.Next(topTracks.Count)];
                    var seedId = seedTrack.GetProperty("id").GetString()!;
                    Console.WriteLine($"🌱 Холодний старт, seed: {seedId}");
                    rawTracks = await spotify.GetRadioTracksAsync(Token, seedId);
                }

                // Якщо радіо порожнє — fallback на search
                if (rawTracks.Count == 0)
                {
                    Console.WriteLine("⚠ Радіо порожнє, використовуємо search");
                    rawTracks = await spotify.SearchTracksAsync(Token, "shoegaze");
                }
            }

            // ── Фільтрація і нормалізація ────────────────────────────────────
            var tracks = rawTracks
                .Where(t =>
                {
                    if (!t.TryGetProperty("id", out var idEl)) return false;
                    var id = idEl.GetString();
                    return id != null && !swiped.Contains(id);
                })
                .DistinctBy(t => t.GetProperty("id").GetString()) // без дублів
                .Take(20)
                .Select(t =>
                {
                    string? albumArt = null;
                    if (t.TryGetProperty("album", out var alb)
                        && alb.TryGetProperty("images", out var imgs)
                        && imgs.GetArrayLength() > 0)
                        albumArt = imgs[0].GetProperty("url").GetString();

                    return new
                    {
                        id        = t.GetProperty("id").GetString(),
                        name      = t.GetProperty("name").GetString(),
                        artist    = t.GetProperty("artists")[0].GetProperty("name").GetString(),
                        album     = t.TryGetProperty("album", out var a)
                                      ? a.GetProperty("name").GetString() : "",
                        albumArt,
                        uri        = t.GetProperty("uri").GetString(),
                        durationMs = t.GetProperty("duration_ms").GetInt32(),
                    };
                })
                .ToList();

            Console.WriteLine($"✅ Повертаємо {tracks.Count} треків");
            return Ok(tracks);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ recommendations: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    // ── GET /api/spotify/profile ──────────────────────────────────────────────
    [HttpGet("profile")]
    public async Task<IActionResult> GetProfile()
    {
        if (string.IsNullOrEmpty(Token)) return Unauthorized();
        try { return Ok(await spotify.GetProfileAsync(Token)); }
        catch (Exception ex) { return StatusCode(500, new { error = ex.Message }); }
    }

    // ── POST /api/spotify/swipe ───────────────────────────────────────────────
    [HttpPost("swipe")]
    public IActionResult RecordSwipe([FromBody] SwipeRequest req)
    {
        storage.AddSwipe(new TrackSwipe(
            req.TrackId, req.TrackName, req.Artist,
            req.AlbumArt, req.Liked, DateTime.UtcNow));
        return Ok(new { success = true });
    }

    // ── GET /api/spotify/swipes ───────────────────────────────────────────────
    [HttpGet("swipes")]
    public IActionResult GetSwipes() => Ok(storage.GetSwipes());
}

public record SwipeRequest(
    string TrackId,
    string TrackName,
    string Artist,
    string? AlbumArt,
    bool Liked);