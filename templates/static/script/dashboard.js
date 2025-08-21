// ===== СКРИПТ ДАШБОРДА =====

window.openChat = function(username) {
    if (username && username !== 'Невідомий' && username !== 'unknown') {
        const encodedUsername = encodeURIComponent(username);
        window.location.href = `/chat/${encodedUsername}`;
    }
};

window.refreshData = function() {
    window.location.reload();
};

window.updateStats = function(data) {
    try {
        const elements = {
            'active-chats-count': data.chat_stats?.active_chats || 0,
            'closed-chats-count': data.chat_stats?.closed_chats || 0,
            'total-users-count': data.chat_stats?.total_users || 0,
            'total-messages-count': data.total_messages || 0
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });

        if (data.chat_stats) {
            updateChatsList(data.chat_stats);
        }
    } catch (error) {
        console.error('Помилка оновлення статистики:', error);
    }
};

window.updateStatsFromAPI = async function() {
    try {
        const data = await window.apiClient.get('/api/stats');
        window.updateStats(data);
    } catch (error) {
        console.error('Помилка оновлення статистики через API:', error);
    }
};

window.refreshMessages = async function() {
    try {
        const data = await window.apiClient.get('/api/recent-messages');
        updateMessagesList(data.messages || []);
    } catch (error) {
        console.error('Помилка оновлення повідомлень:', error);
    }
};

function updateMessagesList(messages) {
    const messagesList = document.getElementById('messagesList');
    if (!messagesList || !Array.isArray(messages)) return;

    if (messages.length === 0) {
        messagesList.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--gray-500);">
                <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                <p>Повідомлення відсутні</p>
            </div>
        `;
        return;
    }

    messagesList.innerHTML = messages.map(msg => {
        const username = window.utils.escapeHtml(msg.username || 'Невідомий');
        const message = window.utils.escapeHtml(window.utils.truncateText(msg.message || ''));
        const time = window.utils.formatTime(msg.timestamp);
        const chatId = msg.chat_id || '';
        const messageType = msg.type || msg.message_type || 'unknown';

        return `
            <div class="message-item message-${messageType}" onclick="openChat('${username}')">
                <div class="message-header">
                    <span class="message-user">
                        <i class="fas fa-arrow-${messageType === 'incoming' ? 'down' : 'up'}" 
                           style="color: ${messageType === 'incoming' ? 'var(--info-color)' : 'var(--success-color)'};"></i>
                        ${username}
                    </span>
                    <div class="flex items-center gap-2">
                        ${chatId ? `<span class="chat-id">#${chatId}</span>` : ''}
                        <span class="message-time">${time}</span>
                    </div>
                </div>
                <div class="message-text">${message}</div>
            </div>
        `;
    }).join('');
}

function updateChatsList(chatStats) {
    const chatsList = document.getElementById('chatsList');
    if (!chatsList || !chatStats) return;
    
    let html = '';
    
    if (chatStats.active_chat_list && Array.isArray(chatStats.active_chat_list)) {
        chatStats.active_chat_list.forEach(chat => {
            const username = window.utils.escapeHtml(chat.username || 'Невідомий');
            const chatId = chat.chat_id || 0;
            const lastActivity = window.utils.formatTime(chat.last_activity);
            
            html += `
                <div class="message-item active-chat" onclick="openChat('${username}')">
                    <div class="message-header">
                        <span class="message-user">
                            <i class="fas fa-circle" style="color: var(--success-color); font-size: 0.6rem;"></i>
                            ${username}
                        </span>
                        <span class="chat-id">#${chatId}</span>
                    </div>
                    <div class="message-time">${lastActivity}</div>
                </div>
            `;
        });
    }
    
    if (chatStats.closed_chat_list && Array.isArray(chatStats.closed_chat_list) && chatStats.closed_chat_list.length > 0) {
        html += `
            <div class="separator">
                <i class="fas fa-history"></i> Закриті чати
            </div>
        `;
        
        chatStats.closed_chat_list.slice(0, 5).forEach(chat => {
            const username = window.utils.escapeHtml(chat.username || 'Невідомий');
            const chatId = chat.chat_id || 0;
            const lastActivity = window.utils.formatTime(chat.last_activity);
            
            html += `
                <div class="message-item closed-chat" onclick="openChat('${username}')">
                    <div class="message-header">
                        <span class="message-user">
                            <i class="fas fa-circle" style="color: var(--danger-color); font-size: 0.6rem;"></i>
                            ${username}
                        </span>
                        <span class="chat-id">#${chatId}</span>
                    </div>
                    <div class="message-time">${lastActivity}</div>
                </div>
            `;
        });
    }
    
    if (!html) {
        html = `
            <div style="text-align: center; padding: 2rem; color: var(--gray-500);">
                <i class="fas fa-comments" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                <p>Чати відсутні</p>
            </div>
        `;
    }
    
    chatsList.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Дашборд ініціалізовано');
    
    setTimeout(() => {
        if (window.showNotification) {
            window.showNotification('Дашборд PulseAi готовий до роботи', 'success');
        }
    }, 1000);
});