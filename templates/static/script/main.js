// ===== ОСНОВНОЙ JAVASCRIPT PULSEAI SUPPORT =====

window.PulseAI = {
    ws: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    config: {
        wsReconnectDelay: 3000,
        notificationTimeout: 3000,
        searchDebounce: 500,
        updateInterval: 30000
    }
};

const Utils = {
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    formatTime(timestamp) {
        if (!timestamp) return 'Невідомо';
        try {
            const date = new Date(timestamp);
            return date.toLocaleTimeString('uk-UA', { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });
        } catch (e) {
            return 'Невідомо';
        }
    },

    truncateText(text, maxLength = 200) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

const Notifications = {
    container: null,

    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notifications-container';
            this.container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            `;
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', duration = 3000) {
        this.init();

        const notification = document.createElement('div');
        notification.className = `notification ${type} show animate-slide-in`;
        notification.style.pointerEvents = 'auto';
        
        const icon = this.getIcon(type);
        notification.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${Utils.escapeHtml(message)}</span>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: inherit; margin-left: auto; cursor: pointer; padding: 0.25rem;">
                <i class="fas fa-times"></i>
            </button>
        `;

        this.container.appendChild(notification);

        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.classList.remove('show');
                    setTimeout(() => notification.remove(), 300);
                }
            }, duration);
        }

        return notification;
    },

    getIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    },

    success(message, duration) {
        return this.show(message, 'success', duration);
    },

    error(message, duration) {
        return this.show(message, 'error', duration);
    },

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    },

    info(message, duration) {
        return this.show(message, 'info', duration);
    }
};

const WebSocketManager = {
    init() {
        this.connect();
    },

    connect() {
        if (window.PulseAI.reconnectAttempts >= window.PulseAI.maxReconnectAttempts) {
            console.error('Максимальное количество попыток переподключения достигнуто');
            this.updateConnectionStatus(false, 'Помилка підключення');
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            window.PulseAI.ws = new WebSocket(wsUrl);

            window.PulseAI.ws.onopen = () => {
                console.log('WebSocket підключено');
                window.PulseAI.reconnectAttempts = 0;
                this.updateConnectionStatus(true, 'Онлайн');
            };

            window.PulseAI.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Помилка обробки повідомлення:', error);
                }
            };

            window.PulseAI.ws.onclose = () => {
                console.log('WebSocket відключено');
                this.updateConnectionStatus(false, 'Відключено');
                this.scheduleReconnect();
            };

            window.PulseAI.ws.onerror = (error) => {
                console.error('WebSocket помилка:', error);
                this.updateConnectionStatus(false, 'Помилка підключення');
            };

        } catch (error) {
            console.error('Не вдалося створити WebSocket:', error);
            this.updateConnectionStatus(false, 'WebSocket недоступний');
            this.scheduleReconnect();
        }
    },

    scheduleReconnect() {
        if (window.PulseAI.reconnectAttempts < window.PulseAI.maxReconnectAttempts) {
            window.PulseAI.reconnectAttempts++;
            const delay = window.PulseAI.config.wsReconnectDelay * window.PulseAI.reconnectAttempts;
            
            this.updateConnectionStatus(false, `Переподключення ${window.PulseAI.reconnectAttempts}/${window.PulseAI.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.connect();
            }, delay);
        }
    },

    handleMessage(data) {
        switch (data.type) {
            case 'update':
                if (window.updateStats) {
                    window.updateStats(data.data);
                }
                break;
            case 'new_message':
                this.handleNewMessage(data);
                break;
            case 'ping':
                break;
            default:
                console.log('Неизвестный тип сообщения:', data.type);
        }
    },

    handleNewMessage(data) {
        Notifications.info(`Нове повідомлення від ${data.username || 'невідомого'}`);
        
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Нове повідомлення PulseAi', {
                body: `${data.username}: ${Utils.truncateText(data.message, 50)}`,
                icon: '/favicon.ico'
            });
        }

        if (window.refreshMessages) {
            window.refreshMessages();
        }
    },

    updateConnectionStatus(connected, text) {
        const indicators = document.querySelectorAll('.status-indicator');
        const statusTexts = document.querySelectorAll('#connection-text');

        indicators.forEach(indicator => {
            indicator.className = connected ? 
                'status-indicator status-online' : 
                'status-indicator status-offline';
        });

        statusTexts.forEach(textElement => {
            if (textElement) {
                textElement.textContent = text;
            }
        });
    }
};

const ApiClient = {
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            }
        };

        const config = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API запит не вдався:', error);
            throw error;
        }
    },

    async get(url) {
        return this.request(url, { method: 'GET' });
    },

    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

const SearchManager = {
    init() {
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', 
                Utils.debounce(this.handleSearch.bind(this), window.PulseAI.config.searchDebounce)
            );
        }
    },

    async handleSearch(event) {
        const query = event.target.value.trim();
        
        if (query.length === 0) {
            this.clearSearch();
            return;
        }

        if (query.length < 2) {
            return;
        }

        try {
            const results = await ApiClient.get(`/search?q=${encodeURIComponent(query)}`);
            this.displayResults(results.results || []);
        } catch (error) {
            console.error('Помилка пошуку:', error);
            Notifications.error('Помилка пошуку');
        }
    },

    displayResults(results) {
        const messagesList = document.getElementById('messagesList');
        if (!messagesList) return;

        if (results.length === 0) {
            messagesList.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: var(--gray-500);">
                    <i class="fas fa-search" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                    <p>Нічого не знайдено</p>
                </div>
            `;
            return;
        }

        messagesList.innerHTML = results.map(result => `
            <div class="message-item message-${result.message_type}" onclick="openChat('${result.username}')">
                <div class="message-header">
                    <span class="message-user">
                        <i class="fas fa-arrow-${result.message_type === 'incoming' ? 'down' : 'up'}" 
                           style="color: ${result.message_type === 'incoming' ? 'var(--info-color)' : 'var(--success-color)'};"></i>
                        ${Utils.escapeHtml(result.username || 'Невідомий')}
                    </span>
                    <div class="flex items-center gap-2">
                        ${result.chat_id ? `<span class="chat-id">#${result.chat_id}</span>` : ''}
                        <span class="message-time">${Utils.formatTime(result.timestamp)}</span>
                    </div>
                </div>
                <div class="message-text">${Utils.escapeHtml(Utils.truncateText(result.message))}</div>
            </div>
        `).join('');
    },

    clearSearch() {
        if (window.refreshMessages) {
            window.refreshMessages();
        }
    }
};

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    console.log('PulseAi Support System загружено');
    
    Notifications.init();
    SearchManager.init();
    WebSocketManager.init();

    // Запрашиваем разрешение на уведомления
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // Периодическое обновление как fallback
    setInterval(() => {
        if (!window.PulseAI.ws || window.PulseAI.ws.readyState !== WebSocket.OPEN) {
            if (window.updateStatsFromAPI) {
                window.updateStatsFromAPI();
            }
        }
    }, window.PulseAI.config.updateInterval);
});

// Глобальные функции
window.showNotification = Notifications.show.bind(Notifications);
window.apiClient = ApiClient;
window.utils = Utils;