export class ApiService 
{
    constructor() 
    {
        this.userId = "test_user_123";
        // потім -> this.baseUrl = 'http://localhost:8000/api/v1';
    }

    async getFeed() 
    {
        // імітація затримки мережі
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // фейкові дані 
        return [
            { track_id: 1, spotify_id: "5vW6hFJrQT90CT4yoNiMWn", name: "Starboy", artist: "The Weeknd" },
            { track_id: 2, spotify_id: "0gDQFz1el7GkcAqBbSCGXX", name: "Bad Guy", artist: "Billie Eilish" },
            { track_id: 3, spotify_id: "3U0TsDX4vzDKtYiGDsz6Bj", name: "Levitating", artist: "Dua Lipa" }
        ];
    }

    async swipe(trackId, direction) 
    {
        console.log(`Sent to backend: Track ${trackId} swiped as ${direction}`);
        // потім -> реальний POST запит
    }
}