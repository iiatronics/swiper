namespace SwiperBack.Models;

public record TrackSwipe(
    string TrackId,
    string TrackName,
    string Artist,
    string? AlbumArt,
    bool Liked,
    DateTime SwipedAt
);

public record PlaylistInfo(
    string PlaylistId,
    string Name,
    DateTime CreatedAt
);

public record AppData(
    List<TrackSwipe> Swipes,
    PlaylistInfo? Playlist
);