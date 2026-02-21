/**
 * nanobot Web Interface
 * Frontend logic for the chat interface
 */

// State management
const state = {
    sessionId: null,
    sessionTitle: null,
    ws: null,
    isConnected: false,
    isTyping: false,
    sessions: [],
    currentMessageElement: null,
    accumulatedResponse: '',
    tasks: new Map(), // Track active tasks
    currentImage: null, // Current selected image (base64)
};

// DOM Elements
const elements = {
    sidebar: document.getElementById('sidebar'),
    sessionsList: document.getElementById('sessionsList'),
    newChatBtn: document.getElementById('newChatBtn'),
    connectionStatus: document.getElementById('connectionStatus'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    menuBtn: document.getElementById('menuBtn'),
    chatTitle: document.getElementById('chatTitle'),
    themeBtn: document.getElementById('themeBtn'),
    messagesContainer: document.getElementById('messagesContainer'),
    welcomeMessage: document.getElementById('welcomeMessage'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    uploadBtn: document.getElementById('uploadBtn'),
    imageInput: document.getElementById('imageInput'),
    imagePreviewContainer: document.getElementById('imagePreviewContainer'),
    imagePreview: document.getElementById('imagePreview'),
    previewImg: document.getElementById('previewImg'),
    removeImageBtn: document.getElementById('removeImageBtn'),
    modelSelect: document.getElementById('modelSelect'),
    modelDescription: document.getElementById('modelDescription'),
};

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    init();
});

function init() {
    console.log('[nanobot] Initializing...');

    // Check if all elements are found
    for (const [name, element] of Object.entries(elements)) {
        if (!element) {
            console.error(`[nanobot] Element not found: ${name}`);
        }
    }

    // Load theme
    loadTheme();

    // Load or create session
    loadSession();

    // Load model preference
    loadModelPreference();

    // Connect WebSocket
    connectWebSocket();

    // Load sessions list
    loadSessions();

    // Setup event listeners
    setupEventListeners();

    // Setup textarea auto-resize
    setupTextarea();

    // Setup model selector
    setupModelSelector();

    console.log('[nanobot] Initialization complete');
}

// Model selector management
function loadModelPreference() {
    const savedModel = localStorage.getItem('selectedModel');
    console.log('[nanobot] Loading model preference:', savedModel);
    if (savedModel && elements.modelSelect) {
        // Only set if it's a valid option
        const validOptions = Array.from(elements.modelSelect.options).map(opt => opt.value);
        if (validOptions.includes(savedModel)) {
            elements.modelSelect.value = savedModel;
            updateModelDescription(savedModel);
            console.log('[nanobot] Model preference loaded:', savedModel);
        } else {
            console.warn('[nanobot] Invalid saved model:', savedModel, 'valid options:', validOptions);
            localStorage.removeItem('selectedModel');
        }
    }
}

function setupModelSelector() {
    if (!elements.modelSelect) return;

    elements.modelSelect.addEventListener('change', (e) => {
        const selectedModel = e.target.value;
        localStorage.setItem('selectedModel', selectedModel);
        updateModelDescription(selectedModel);
        console.log('[nanobot] Model changed to:', selectedModel);
    });
}

function updateModelDescription(model) {
    if (!elements.modelDescription) return;

    const descriptions = {
        'qwen': '支持视觉理解的统一多模态模型',
        'minimax': '支持搜索和视觉理解工具',
    };
    elements.modelDescription.textContent = descriptions[model] || '';
}

function getSelectedModel() {
    if (!elements.modelSelect) {
        console.error('[nanobot] modelSelect element not found!');
        return 'qwen';
    }
    const value = elements.modelSelect.value;
    console.log('[nanobot] getSelectedModel returning:', value);
    return value;
}

// Theme management
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    elements.themeBtn.textContent = savedTheme === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    elements.themeBtn.textContent = newTheme === 'dark' ? '☀️' : '🌙';
}

// Session management
function loadSession() {
    const savedSessionId = localStorage.getItem('currentSessionId');
    if (savedSessionId) {
        state.sessionId = savedSessionId;
        // Restore session title
        state.sessionTitle = localStorage.getItem(`sessionTitle_${savedSessionId}`);
        if (state.sessionTitle) {
            elements.chatTitle.textContent = truncateTitle(state.sessionTitle);
        }
        loadSessionHistory(savedSessionId);
    } else {
        createNewSession();
    }
}

// Truncate title to max 20 chars
function truncateTitle(text) {
    if (!text) return '新对话';
    return text.length > 20 ? text.slice(0, 20) + '...' : text;
}

function createNewSession() {
    state.sessionId = generateId();
    state.sessionTitle = null; // Reset title
    localStorage.setItem('currentSessionId', state.sessionId);
    localStorage.removeItem(`sessionTitle_${state.sessionId}`);
    elements.chatTitle.textContent = '新对话';

    // Clear messages but keep welcome message reference valid
    elements.messagesContainer.innerHTML = '';

    // Re-create welcome message to ensure it's in DOM
    const welcomeHTML = `
        <div class="welcome-message" id="welcomeMessage">
            <div class="welcome-icon">🤖</div>
            <h2>你好！我是 nanobot</h2>
            <p>你的个人 AI 助手。有什么我可以帮助你的吗？</p>
        </div>
    `;
    elements.messagesContainer.innerHTML = welcomeHTML;

    // Update reference
    elements.welcomeMessage = document.getElementById('welcomeMessage');
}

async function loadSessionHistory(sessionId) {
    try {
        const response = await fetch(`/api/sessions/web:${sessionId}/history`);
        const messages = await response.json();

        // Clear and prepare container
        elements.messagesContainer.innerHTML = '';

        // Re-add welcome message (hidden)
        const welcomeHTML = `
            <div class="welcome-message" id="welcomeMessage" style="display: none;">
                <div class="welcome-icon">🤖</div>
                <h2>你好！我是 nanobot</h2>
                <p>你的个人 AI 助手。有什么我可以帮助你的吗？</p>
            </div>
        `;
        elements.messagesContainer.innerHTML = welcomeHTML;
        elements.welcomeMessage = document.getElementById('welcomeMessage');

        // Show messages or welcome
        if (messages.length === 0) {
            elements.welcomeMessage.style.display = 'block';
        } else {
            messages.forEach(msg => {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    appendMessage(msg.role, msg.content, false);
                }
            });
        }

        scrollToBottom();
    } catch (error) {
        console.error('Failed to load session history:', error);
    }
}

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        state.sessions = await response.json();
        renderSessionsList();
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

function renderSessionsList() {
    elements.sessionsList.innerHTML = '';

    state.sessions.forEach(session => {
        // Extract session ID from key (web:xxx -> xxx)
        const sessionId = session.key.replace('web:', '');
        const isActive = sessionId === state.sessionId;

        // Get saved title for this session
        const savedTitle = localStorage.getItem(`sessionTitle_${sessionId}`);
        // Use title (first message) if available, otherwise use shortened session ID
        const displayTitle = savedTitle ? truncateTitle(savedTitle) : `会话 ${sessionId.slice(0, 6)}`;

        const item = document.createElement('div');
        item.className = `session-item ${isActive ? 'active' : ''}`;
        item.dataset.sessionId = sessionId;

        const date = new Date(session.updated_at);
        const timeStr = formatTime(date);

        item.innerHTML = `
            <div class="session-info">
                <div class="session-title">${displayTitle}</div>
                <div class="session-time">${timeStr}</div>
            </div>
            <button class="session-delete" title="删除会话">×</button>
        `;

        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('session-delete')) {
                e.stopPropagation();
                deleteSession(sessionId);
            } else {
                switchSession(sessionId);
            }
        });

        elements.sessionsList.appendChild(item);
    });
}

async function switchSession(sessionId) {
    state.sessionId = sessionId;
    // Restore session title
    state.sessionTitle = localStorage.getItem(`sessionTitle_${sessionId}`);
    elements.chatTitle.textContent = state.sessionTitle ? truncateTitle(state.sessionTitle) : '新对话';
    localStorage.setItem('currentSessionId', sessionId);
    await loadSessionHistory(sessionId);
    renderSessionsList();
}

async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) return;

    try {
        await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });

        // Remove saved title from localStorage
        localStorage.removeItem(`sessionTitle_${sessionId}`);

        if (sessionId === state.sessionId) {
            state.sessionTitle = null;
            createNewSession();
        }

        await loadSessions();
    } catch (error) {
        console.error('Failed to delete session:', error);
    }
}

// WebSocket management
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log(`[nanobot] Connecting to WebSocket: ${wsUrl}`);

    try {
        state.ws = new WebSocket(wsUrl);
    } catch (error) {
        console.error('[nanobot] Failed to create WebSocket:', error);
        return;
    }

    state.ws.onopen = () => {
        console.log('[nanobot] WebSocket connected');
        state.isConnected = true;
        updateConnectionStatus(true);
    };

    state.ws.onclose = (event) => {
        console.log(`[nanobot] WebSocket closed: code=${event.code}, reason=${event.reason}`);
        state.isConnected = false;
        updateConnectionStatus(false);
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };

    state.ws.onerror = (error) => {
        console.error('[nanobot] WebSocket error:', error);
    };

    state.ws.onmessage = (event) => {
        console.log('[nanobot] WebSocket message received:', event.data);
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('[nanobot] Failed to parse WebSocket message:', error);
        }
    };
}

function updateConnectionStatus(connected) {
    state.isConnected = connected;
    elements.statusDot.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
    elements.statusText.textContent = connected ? '已连接' : '未连接';
}

function handleWebSocketMessage(data) {
    console.log(`[nanobot] Handling message type: ${data.type}`, data);

    switch (data.type) {
        case 'ack':
            console.log('[nanobot] Acknowledgment received');
            break;

        case 'chunk':
            handleChunk(data.content);
            break;

        case 'complete':
            handleComplete(data.full_response);
            break;

        case 'error':
            handleError(data.message);
            break;

        case 'task_update':
            handleTaskUpdate(data.task);
            break;

        case 'pong':
            // Ping-pong keepalive
            break;

        default:
            console.warn(`[nanobot] Unknown message type: ${data.type}`);
    }
}

function handleChunk(content) {
    console.log(`[nanobot] handleChunk called with content length: ${content?.length || 0}`);

    if (!state.currentMessageElement) {
        console.log('[nanobot] Creating new assistant message element');

        // Hide welcome message if it exists
        const welcomeMsg = document.getElementById('welcomeMessage');
        if (welcomeMsg) {
            welcomeMsg.style.display = 'none';
        }

        state.currentMessageElement = createMessageElement('assistant', '');
        elements.messagesContainer.appendChild(state.currentMessageElement);
        console.log('[nanobot] Element appended to container');
    }

    state.accumulatedResponse += content;
    console.log(`[nanobot] Accumulated response length: ${state.accumulatedResponse.length}`);

    const messageBody = state.currentMessageElement.querySelector('.message-body');
    console.log('[nanobot] messageBody element:', messageBody);
    if (!messageBody) {
        console.error('[nanobot] Message body element not found!');
        return;
    }

    try {
        const rendered = renderMarkdown(state.accumulatedResponse);
        console.log('[nanobot] Rendered HTML length:', rendered.length);
        messageBody.innerHTML = rendered;
        console.log('[nanobot] Message rendered successfully');
    } catch (error) {
        console.error('[nanobot] Error rendering markdown:', error);
        // Fallback to plain text
        messageBody.textContent = state.accumulatedResponse;
    }

    // Highlight code blocks
    if (typeof hljs !== 'undefined') {
        messageBody.querySelectorAll('pre code').forEach((block) => {
            try {
                hljs.highlightElement(block);
            } catch (e) {
                console.warn('[nanobot] Error highlighting code block:', e);
            }
        });
    }

    scrollToBottom(true);  // 强制滚动到底部
}

function handleComplete(fullResponse) {
    console.log('[nanobot] Response complete, length:', fullResponse?.length || 0);
    state.isTyping = false;
    state.currentMessageElement = null;
    state.accumulatedResponse = '';

    // Update sessions list
    loadSessions();
}

function handleError(message) {
    state.isTyping = false;
    state.currentMessageElement = null;
    state.accumulatedResponse = '';

    appendMessage('assistant', `❌ 错误: ${message}`, false);
}

// Task update handling
function handleTaskUpdate(task) {
    console.log('[nanobot] Task update received:', task);

    const { task_id, title, description, status, progress, error } = task;

    // Find or create task element
    let taskElement = document.getElementById(`task-${task_id}`);

    if (!taskElement) {
        // Create new task element
        taskElement = createTaskElement(task_id, title);

        // Insert after the last message or at the beginning
        if (elements.messagesContainer.lastElementChild) {
            elements.messagesContainer.insertBefore(taskElement, elements.messagesContainer.lastElementChild.nextSibling);
        } else {
            elements.messagesContainer.appendChild(taskElement);
        }

        // Store task reference
        state.tasks.set(task_id, task);
    }

    // Update task display
    updateTaskElement(taskElement, task);

    // Remove completed/failed tasks from tracking after a delay
    if (status === 'completed' || status === 'failed') {
        setTimeout(() => {
            state.tasks.delete(task_id);
        }, 5000);
    }

    scrollToBottom();
}

function createTaskElement(taskId, title) {
    const element = document.createElement('div');
    element.id = `task-${taskId}`;
    element.className = 'task-item';
    element.innerHTML = `
        <div class="task-header">
            <span class="task-icon">⚙️</span>
            <span class="task-title">${escapeHtml(title)}</span>
            <span class="task-status">pending</span>
        </div>
        <div class="task-progress-container">
            <div class="task-progress-bar">
                <div class="task-progress-fill" style="width: 0%"></div>
            </div>
            <span class="task-progress-text">0%</span>
        </div>
        <div class="task-description"></div>
    `;
    return element;
}

function updateTaskElement(element, task) {
    const { status, progress, error, description } = task;

    // Update status icon
    const iconEl = element.querySelector('.task-icon');
    const statusEl = element.querySelector('.task-status');

    if (status === 'completed') {
        iconEl.textContent = '✅';
        statusEl.textContent = '已完成';
        statusEl.className = 'task-status status-completed';
    } else if (status === 'failed') {
        iconEl.textContent = '❌';
        statusEl.textContent = '失败';
        statusEl.className = 'task-status status-failed';
    } else if (status === 'running') {
        iconEl.textContent = '⚙️';
        statusEl.textContent = '运行中';
        statusEl.className = 'task-status status-running';
    } else {
        iconEl.textContent = '⏳';
        statusEl.textContent = '等待中';
        statusEl.className = 'task-status status-pending';
    }

    // Update progress bar
    const progressFill = element.querySelector('.task-progress-fill');
    const progressText = element.querySelector('.task-progress-text');
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;

    // Update description
    const descEl = element.querySelector('.task-description');
    if (error) {
        descEl.textContent = `错误: ${error}`;
        descEl.className = 'task-description error';
    } else if (description) {
        descEl.textContent = description;
        descEl.className = 'task-description';
    }
}

// Message handling
function sendMessage() {
    console.log('[nanobot] sendMessage called');
    console.log('[nanobot] messageInput element:', elements.messageInput);
    console.log('[nanobot] messageInput value:', elements.messageInput?.value);

    if (!elements.messageInput) {
        console.error('[nanobot] messageInput is null!');
        return;
    }

    const content = elements.messageInput.value.trim();
    const hasImage = !!state.currentImage;

    console.log(`[nanobot] Message content: "${content}", hasImage: ${hasImage}, isTyping: ${state.isTyping}, isConnected: ${state.isConnected}`);

    // Allow sending if there's text OR image
    if ((!content && !hasImage) || state.isTyping) {
        console.log('[nanobot] Message not sent: empty or already typing');
        return;
    }

    // Clear input
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';

    // Hide welcome message
    const welcomeMsg = document.getElementById('welcomeMessage');
    if (welcomeMsg) {
        welcomeMsg.style.display = 'none';
    }

    // Save first message as session title (use text or '图片' as title)
    if (!state.sessionTitle) {
        state.sessionTitle = content || '图片消息';
        localStorage.setItem(`sessionTitle_${state.sessionId}`, state.sessionTitle);
        elements.chatTitle.textContent = truncateTitle(state.sessionTitle);
        // Update sessions list to show new title
        loadSessions();
    }

    // Add user message with image if present
    const displayContent = hasImage
        ? (content ? `${content}\n\n[图片]` : '[图片]')
        : content;
    appendMessage('user', displayContent, true);

    // If has image, append image element
    if (hasImage) {
        appendImageToLastMessage(state.currentImage);
    }

    scrollToBottom(true);  // 强制滚动到底部

    // Send via WebSocket
    console.log('[nanobot] About to check isConnected:', state.isConnected);
    if (state.isConnected) {
        console.log('[nanobot] Entering isConnected block');
        state.isTyping = true;
        state.accumulatedResponse = '';

        console.log('[nanobot] Calling getSelectedModel...');
        const selectedModel = getSelectedModel();
        console.log('[nanobot] Selected model:', selectedModel);
        console.log('[nanobot] modelSelect element value:', elements.modelSelect?.value);
        console.log('[nanobot] modelSelect element:', elements.modelSelect);

        const messageData = {
            type: 'chat',
            session_id: state.sessionId,
            message: content,
            model: selectedModel,
        };

        // Include image if present
        if (hasImage) {
            messageData.image = state.currentImage;
        }

        const jsonStr = JSON.stringify(messageData);
        console.log('[nanobot] Sending WebSocket message:', jsonStr);
        state.ws.send(jsonStr);

        // Clear image after sending
        clearImageSelection();
    } else {
        appendMessage('assistant', '⚠️ 未连接到服务器，请稍后重试。', false);
    }
}

function appendImageToLastMessage(imageData) {
    const messages = elements.messagesContainer.querySelectorAll('.message.user');
    if (messages.length === 0) return;

    const lastMessage = messages[messages.length - 1];
    const messageBody = lastMessage.querySelector('.message-body');
    if (!messageBody) return;

    const img = document.createElement('img');
    img.src = imageData;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '200px';
    img.style.borderRadius = '8px';
    img.style.marginTop = '8px';
    img.style.display = 'block';
    messageBody.appendChild(img);
}

function appendMessage(role, content, animate = true) {
    const element = createMessageElement(role, content);

    if (animate) {
        element.style.animation = 'messageIn 0.3s ease';
    }

    elements.messagesContainer.appendChild(element);
    scrollToBottom();

    return element;
}

function createMessageElement(role, content) {
    const message = document.createElement('div');
    message.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const author = role === 'user' ? '你' : 'nanobot';
    const time = formatTime(new Date());

    message.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">${author}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-body">${content ? renderMarkdown(content) : '<div class="typing-indicator"><span></span><span></span><span></span></div>'}</div>
        </div>
    `;

    return message;
}

function renderMarkdown(text) {
    // Check if marked is loaded
    if (typeof marked === 'undefined') {
        console.warn('[nanobot] marked library not loaded, returning plain text');
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    try {
        // Configure marked
        marked.setOptions({
            breaks: true,
            gfm: true,
        });

        // Render markdown
        return marked.parse(text);
    } catch (error) {
        console.error('[nanobot] Error in marked.parse:', error);
        return escapeHtml(text).replace(/\n/g, '<br>');
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
function setupEventListeners() {
    // New chat button
    elements.newChatBtn.addEventListener('click', () => {
        createNewSession();
        renderSessionsList();
    });

    // Menu button (mobile)
    elements.menuBtn.addEventListener('click', () => {
        elements.sidebar.classList.toggle('collapsed');
    });

    // Theme button
    elements.themeBtn.addEventListener('click', toggleTheme);

    // Send button
    elements.sendBtn.addEventListener('click', sendMessage);

    // Enter to send, Shift+Enter for new line
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Scroll event to show/hide scroll to bottom button
    elements.messagesContainer.addEventListener('scroll', () => {
        updateScrollButton();
    });

    // Image upload handlers
    if (elements.uploadBtn) {
        elements.uploadBtn.addEventListener('click', () => {
            elements.imageInput?.click();
        });
    }

    if (elements.imageInput) {
        elements.imageInput.addEventListener('change', handleImageSelect);
    }

    if (elements.removeImageBtn) {
        elements.removeImageBtn.addEventListener('click', clearImageSelection);
    }
}

// Image handling functions
function handleImageSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Check file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
        alert('图片大小不能超过 5MB');
        return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
        state.currentImage = event.target.result;
        showImagePreview(state.currentImage);
    };
    reader.readAsDataURL(file);
}

function showImagePreview(imageData) {
    if (!elements.previewImg || !elements.imagePreviewContainer) return;

    elements.previewImg.src = imageData;
    elements.imagePreviewContainer.style.display = 'block';
    elements.uploadBtn?.classList.add('has-image');
}

function clearImageSelection() {
    state.currentImage = null;
    if (elements.imagePreviewContainer) {
        elements.imagePreviewContainer.style.display = 'none';
    }
    if (elements.previewImg) {
        elements.previewImg.src = '';
    }
    if (elements.imageInput) {
        elements.imageInput.value = '';
    }
    elements.uploadBtn?.classList.remove('has-image');
}

function setupTextarea() {
    const textarea = elements.messageInput;

    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    });
}

// Utility functions
function scrollToBottom(force = false) {
    const container = elements.messagesContainer;
    const threshold = 100; // pixels from bottom
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;

    // Only scroll if user is near bottom or force is true
    if (force || isNearBottom) {
        container.scrollTop = container.scrollHeight;
    }
}

// Check if should show scroll to bottom button
function updateScrollButton() {
    const container = elements.messagesContainer;
    const threshold = 100;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;

    let scrollBtn = document.getElementById('scrollToBottomBtn');

    if (!isNearBottom) {
        if (!scrollBtn) {
            scrollBtn = document.createElement('button');
            scrollBtn.id = 'scrollToBottomBtn';
            scrollBtn.innerHTML = '↓';
            scrollBtn.title = '滚动到底部';
            scrollBtn.style.cssText = `
                position: fixed;
                bottom: 100px;
                right: 30px;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: var(--primary);
                color: white;
                border: none;
                cursor: pointer;
                font-size: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                z-index: 100;
                transition: opacity 0.3s;
            `;
            scrollBtn.onclick = () => scrollToBottom(true);
            document.body.appendChild(scrollBtn);
        }
        scrollBtn.style.opacity = '1';
    } else if (scrollBtn) {
        scrollBtn.style.opacity = '0';
        setTimeout(() => scrollBtn?.remove(), 300);
    }
}

function generateId() {
    return Math.random().toString(36).substring(2, 10);
}

function formatTime(date) {
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return '刚刚';
    }

    // Less than 1 hour
    if (diff < 3600000) {
        return `${Math.floor(diff / 60000)}分钟前`;
    }

    // Less than 24 hours
    if (diff < 86400000) {
        return `${Math.floor(diff / 3600000)}小时前`;
    }

    // Format date
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hour = date.getHours().toString().padStart(2, '0');
    const minute = date.getMinutes().toString().padStart(2, '0');

    return `${month}-${day} ${hour}:${minute}`;
}

// Ping keepalive
setInterval(() => {
    if (state.isConnected && state.ws) {
        state.ws.send(JSON.stringify({ type: 'ping' }));
    }
}, 30000);
