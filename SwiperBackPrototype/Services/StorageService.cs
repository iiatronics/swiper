using System.Text.Json;
using SwiperBack.Models;

namespace SwiperBack.Services;

public class StorageService
{
    private readonly string _path;
    private readonly JsonSerializerOptions _opts = new() { WriteIndented = true };
    private readonly object _lock = new();

    public StorageService(IConfiguration cfg)
    {
        _path = cfg["DataPath"] ?? Path.Combine(AppContext.BaseDirectory, "data.json");
        Console.WriteLine($"📁 Storage: {_path}");
    }

    private AppData Load()
    {
        lock (_lock)
        {
            try
            {
                if (!File.Exists(_path)) return new AppData([], null);
                var json = File.ReadAllText(_path);
                return JsonSerializer.Deserialize<AppData>(json, _opts)
                       ?? new AppData([], null);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"⚠ Load failed: {ex.Message}");
                return new AppData([], null);
            }
        }
    }

    private void Save(AppData data)
    {
        lock (_lock)
        {
            var dir = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(_path, JsonSerializer.Serialize(data, _opts));
        }
    }

    public List<TrackSwipe> GetSwipes() => Load().Swipes;

    public List<string> GetLikedIds() =>
        Load().Swipes.Where(s => s.Liked).Select(s => s.TrackId).ToList();

    public HashSet<string> GetAllSwipedIds() =>
        Load().Swipes.Select(s => s.TrackId).ToHashSet();

    public void AddSwipe(TrackSwipe swipe)
    {
        var data = Load();
        var swipes = data.Swipes.Where(s => s.TrackId != swipe.TrackId).ToList();
        swipes.Add(swipe);
        Save(data with { Swipes = swipes });
    }

    public PlaylistInfo? GetPlaylist() => Load().Playlist;

    public void SavePlaylist(PlaylistInfo p) =>
        Save(Load() with { Playlist = p });
}