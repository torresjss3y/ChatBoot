let isTyping = false;

// En static/script.js - actualizar la función sendMessage

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || isTyping) return;
    
    input.value = '';
    const sendButton = document.getElementById('sendButton');
    sendButton.disabled = true;
    
    addMessage(message, 'user');
    showTypingIndicator();
    isTyping = true;
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            // ✅ Añadir opción para forzar refresh si se desea
            body: JSON.stringify({ 
                mensaje: message,
                force_refresh: false  // Cambiar a true para forzar actualización
            })
        });
        
        if (!response.ok) {
            throw new Error(`Error: ${response.status}`);
        }
        
        const data = await response.json();
        
        removeTypingIndicator();
        isTyping = false;
        
        // ✅ Mostrar respuesta con indicador de fuente
        addMessage(data.respuesta, 'bot', data.fuente);
        
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator();
        isTyping = false;
        addMessage('Lo siento, hubo un error al procesar tu mensaje. Por favor, intenta de nuevo. 😅', 'bot');
    } finally {
        sendButton.disabled = false;
        input.focus();
        scrollToBottom();
    }
}

// ✅ Función actualizada para mostrar fuente
function addMessage(text, sender, fuente) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    const avatar = sender === 'user' ? '👤' : '🤖';
    
    let fuenteHtml = '';
    if (fuente && sender === 'bot') {
        fuenteHtml = `<div style="font-size: 10px; color: #6c757d; margin-top: 2px; padding-left: 52px;">
            📍 Fuente: ${fuente}
        </div>`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-avatar">${avatar}</div>
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
        <div class="message-time">${timeString}</div>
        ${fuenteHtml}
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

// Función para mostrar indicador de escritura
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typingIndicator';
    typingDiv.className = 'message bot';
    typingDiv.innerHTML = `
        <div class="message-content">
            <div class="message-avatar">🤖</div>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

// Función para quitar indicador de escritura
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Función para limpiar el chat
function clearChat() {
    if (confirm('¿Estás seguro de que quieres limpiar la conversación?')) {
        const messagesContainer = document.getElementById('chatMessages');
        // Mantener solo el mensaje de bienvenida
        messagesContainer.innerHTML = `
            <div class="message bot">
                <div class="message-content">
                    <div class="message-avatar">🤖</div>
                    <div class="message-text">
                        ¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy? 😊
                    </div>
                </div>
                <div class="message-time">Ahora</div>
            </div>
        `;
        // También limpiar el historial del servidor si existe
        fetch('/historial', { method: 'DELETE' }).catch(() => {});
    }
}

// Función para manejar la tecla Enter
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Función para hacer scroll al final del chat
function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Función para escapar HTML y prevenir XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Auto-focus al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('messageInput').focus();
});

// Enviar mensaje con Ctrl+Enter o Cmd+Enter
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        sendMessage();
    }
});