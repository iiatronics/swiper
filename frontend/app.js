import { ApiService } from './api.js';

console.log("1. Файл app.js успішно підключився!");

class UIController {
    constructor() {
        console.log("2. Запускаємо UIController...");
        this.api = new ApiService();
        this.tracks = [];
        this.container = document.getElementById('card-container');
        
        console.log("3. Чи знайшов HTML-контейнер?:", this.container);
        
        this.init();
        this.setupButtons();
    }

    async init() {
        console.log("4. Починаємо завантаження даних...");
        if (this.container) {
            this.container.innerHTML = '<p class="text-[#1DB954]">Loading tracks...</p>';
        }
        
        this.tracks = await this.api.getFeed();
        console.log("5. Дані отримано! Ось вони:", this.tracks);
        
        this.renderCards();
    }

    renderCards() {
        console.log("6. Починаємо малювати картку...");
        if (!this.container) return;
        
        this.container.innerHTML = ''; 
        
        if (this.tracks.length === 0) {
            console.log("7. Треки закінчилися.");
            this.container.innerHTML = '<p class="text-zinc-500">No more tracks</p>';
            return;
        }

        const currentTrack = this.tracks[0];
        console.log("8. Малюємо трек:", currentTrack.name);

        const cardElement = document.createElement('div');
        cardElement.className = 'card absolute w-80 h-96 bg-zinc-900 rounded-2xl shadow-xl border border-zinc-800 flex flex-col items-center p-6 text-center';
        
        cardElement.innerHTML = `
            <div class="w-full h-64 bg-zinc-800 rounded-lg mb-4 overflow-hidden shadow-lg">
                <img src="https://picsum.photos/seed/${currentTrack.spotify_id}/400/400" alt="Cover" class="w-full h-full object-cover" />
            </div>
            <h2 class="text-2xl font-bold text-white mb-1">${currentTrack.name}</h2>
            <p class="text-zinc-400 text-lg">${currentTrack.artist}</p>
        `;

        this.container.appendChild(cardElement);
        console.log("9. Картку успішно додано на екран!");
    }

    async handleAction(direction) {
        if (this.tracks.length === 0) return;
        const currentTrack = this.tracks.shift(); 
        
        const card = this.container.querySelector('.card');
        if (card) {
            card.style.transform = direction === 'like' ? 'translateX(100vw) rotate(20deg)' : 'translateX(-100vw) rotate(-20deg)';
            card.style.opacity = '0';
        }

        await this.api.swipe(currentTrack.track_id, direction);
        setTimeout(() => this.renderCards(), 300);
    }

    setupButtons() {
        const btnLike = document.getElementById('btn-like');
        const btnDislike = document.getElementById('btn-dislike');
        
        if (btnLike && btnDislike) {
            btnLike.addEventListener('click', () => this.handleAction('like'));
            btnDislike.addEventListener('click', () => this.handleAction('dislike'));
            console.log("Кнопки підключено успішно.");
        } else {
            console.error("Помилка: Не можу знайти кнопки в HTML!");
        }
    }
}

new UIController();