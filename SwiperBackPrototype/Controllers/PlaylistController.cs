using Microsoft.AspNetCore.Mvc;
using SwiperBack.Models;
using SwiperBack.Services;

namespace SwiperBack.Controllers;

[ApiController]
[Route("api/playlist")]
public class PlaylistController(SpotifyService spotify, StorageService storage) : ControllerBase
{
    private string Token =>
        Request.Headers.Authorization.ToString().Replace("Bearer ", "").Trim();

    [HttpPost("sync")]
    public async Task<IActionResult> Sync()
    {
        if (string.IsNullOrEmpty(Token)) return Unauthorized();
        try
        {
            var likedIds = storage.GetLikedIds();
            if (likedIds.Count == 0)
                return BadRequest(new { error = "Немає лайкнутих треків" });

            var profile  = await spotify.GetProfileAsync(Token);
            var userId   = profile.GetProperty("id").GetString()!;

            var existing = storage.GetPlaylist();
            string playlistId;

            if (existing == null)
            {
                playlistId = await spotify.CreatePlaylistAsync(Token, userId, "💚 Swiper Likes");
                storage.SavePlaylist(new PlaylistInfo(playlistId, "💚 Swiper Likes", DateTime.UtcNow));
            }
            else
            {
                playlistId = existing.PlaylistId;
            }

            var inPlaylist = await spotify.GetPlaylistTrackIdsAsync(Token, playlistId);
            var toAdd = likedIds.Where(id => !inPlaylist.Contains(id)).ToList();

            if (toAdd.Count > 0)
                await spotify.AddToPlaylistAsync(Token, playlistId, toAdd);

            return Ok(new
            {
                playlistId,
                tracksAdded = toAdd.Count,
                totalLiked  = likedIds.Count,
                spotifyUrl  = $"https://open.spotify.com/playlist/{playlistId}"
            });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ playlist/sync: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    [HttpGet("info")]
    public IActionResult Info() => Ok(storage.GetPlaylist());
}