<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Toolkit</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        .chat-bubble { max-width: 90%; word-wrap: break-word; white-space: pre-wrap; }
        .user-bubble { background-color: #2563eb; color: white; }
        .ai-bubble { background-color: #334155; color: #f1f5f9; }
        #chat-sidebar { transition: transform 0.3s ease-in-out; }
        .tab-button.active { border-color: #4f46e5; color: #4f46e5; }
        
        #chat-container::-webkit-scrollbar, #chat-container-ai::-webkit-scrollbar, #saved-chats-list::-webkit-scrollbar { width: 8px; }
        #chat-container::-webkit-scrollbar-track, #chat-container-ai::-webkit-scrollbar-track, #saved-chats-list::-webkit-scrollbar-track { background: #1e293b; }
        #chat-container::-webkit-scrollbar-thumb, #chat-container-ai::-webkit-scrollbar-thumb, #saved-chats-list::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
        
        /* Styles for code blocks and the copy button */
        .ai-bubble pre {
            background-color: #0f172a; /* Even darker blue */
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            position: relative;
        }
        .ai-bubble code {
            font-family: 'Courier New', Courier, monospace;
        }
        .copy-button {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background-color: #475569;
            color: white;
            border: none;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            cursor: pointer;
            font-size: 0.8rem;
            opacity: 0;
            transition: opacity 0.2s;
        }
        pre:hover .copy-button {
            opacity: 1;
        }
    </style>
</head>
<body class="bg-gray-100 h-screen overflow-hidden">

    <div class="flex h-full">
        <aside id="chat-sidebar" class="w-64 bg-slate-800 text-white flex flex-col p-4 transform -translate-x-full fixed h-full z-20">
            <div class="flex justify-between items-center mb-4 border-b border-slate-600 pb-2">
                <h2 id="sidebar-title" class="text-xl font-bold">Saved Chats</h2>
                <button id="close-sidebar-button" class="text-slate-400 hover:text-white text-2xl">&times;</button>
            </div>
            <button id="new-chat-button" class="w-full text-left p-2 mb-2 bg-indigo-500 rounded-md hover:bg-indigo-600">＋ New Chat</button>
            <div id="saved-chats-list" class="flex-1 overflow-y-auto space-y-2"></div>
        </aside>

        <div class="flex-1 flex flex-col h-full">
             <header class="bg-white shadow-md p-4 flex items-center justify-between z-10">
                <div class="flex items-center space-x-4">
                    <button id="open-sidebar-button" class="p-2 rounded-md hover:bg-gray-200">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
                    </button>
                    <div>
                        <h1 class="text-2xl font-bold text-gray-800">AI Toolkit</h1>
                        <p id="status" class="text-sm text-gray-500">Status: Connecting to server...</p>
                    </div>
                </div>
                <div>
                    <button id="tab-chatpdf" class="tab-button py-2 px-4 text-gray-500 font-semibold border-b-2">ChatPDF</button>
                    <button id="tab-ai-chat" class="tab-button py-2 px-4 text-gray-500 font-semibold border-b-2">AI Chat</button>
                </div>
            </header>

            <div id="view-chatpdf" class="flex-1 grid grid-cols-2 gap-4 p-4 overflow-hidden">
                <section class="bg-white rounded-lg shadow-md flex flex-col h-full">
                    <div class="p-2 border-b bg-gray-50"><h2 id="pdf-title" class="text-lg font-bold text-gray-700 truncate">PDF Preview</h2></div>
                    <div class="flex-1 p-2"><embed id="pdf-viewer" src="" type="application/pdf" width="100%" height="100%"/></div>
                </section>
                <section class="bg-slate-800 rounded-lg shadow-md flex flex-col h-full overflow-hidden">
                    <main id="chat-container" class="flex-1 p-4 space-y-4 overflow-y-auto"></main>
                    <footer class="bg-slate-900/50 p-4 border-t border-slate-700">
                        <div class="flex items-center space-x-4">
                            <div>
                                <label for="pdf-upload" id="upload-label" class="cursor-not-allowed bg-gray-500 text-white font-bold py-2 px-4 rounded-lg">📁 Upload</label>
                                <input id="pdf-upload" type="file" class="hidden" accept=".pdf" disabled>
                            </div>
                            <input type="text" id="message-input" class="flex-1 bg-slate-700 border border-slate-600 text-white rounded-lg p-2" placeholder="Please connect to worker..." disabled>
                            <button id="send-button" class="bg-gray-500 text-white font-bold py-2 px-4 rounded-lg" disabled>Send</button>
                            <button id="save-chat-button-pdf" class="bg-indigo-500 text-white font-bold py-2 px-4 rounded-lg opacity-50 cursor-not-allowed" disabled>Save</button>
                        </div>
                    </footer>
                </section>
            </div>

            <div id="view-ai-chat" style="display: none;" class="flex-1 flex flex-col p-4 overflow-hidden">
                <section class="bg-slate-800 rounded-lg shadow-md flex flex-col h-full overflow-hidden">
                    <main id="chat-container-ai" class="flex-1 p-4 space-y-4 overflow-y-auto"></main>
                    <footer class="bg-slate-900/50 p-4 border-t border-slate-700">
                        <div class="flex items-center space-x-4">
                            <input type="text" id="message-input-ai" class="flex-1 bg-slate-700 border border-slate-600 text-white rounded-lg p-2" placeholder="Please connect to worker..." disabled>
                            <button id="send-button-ai" class="bg-gray-500 text-white font-bold py-2 px-4 rounded-lg" disabled>Send</button>
                            <button id="save-chat-button-ai" class="bg-indigo-500 text-white font-bold py-2 px-4 rounded-lg opacity-50 cursor-not-allowed" disabled>Save</button>
                        </div>
                    </footer>
                </section>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const ui = {
                status: document.getElementById('status'),
                sidebar: document.getElementById('chat-sidebar'),
                sidebarTitle: document.getElementById('sidebar-title'),
                openSidebarButton: document.getElementById('open-sidebar-button'),
                closeSidebarButton: document.getElementById('close-sidebar-button'),
                newChatButton: document.getElementById('new-chat-button'),
                savedChatsList: document.getElementById('saved-chats-list'),
                
                tabChatPDF: document.getElementById('tab-chatpdf'),
                tabAIChat: document.getElementById('tab-ai-chat'),
                viewChatPDF: document.getElementById('view-chatpdf'),
                viewAIChat: document.getElementById('view-ai-chat'),

                chatContainer: document.getElementById('chat-container'),
                messageInput: document.getElementById('message-input'),
                sendButton: document.getElementById('send-button'),
                saveChatButtonPDF: document.getElementById('save-chat-button-pdf'),
                pdfUploadInput: document.getElementById('pdf-upload'),
                uploadLabel: document.getElementById('upload-label'),
                pdfViewer: document.getElementById('pdf-viewer'),
                pdfTitle: document.getElementById('pdf-title'),

                chatContainerAI: document.getElementById('chat-container-ai'),
                messageInputAI: document.getElementById('message-input-ai'),
                sendButtonAI: document.getElementById('send-button-ai'),
                saveChatButtonAI: document.getElementById('save-chat-button-ai'),
            };
            
            let userId = localStorage.getItem('ai_toolkit_user_id') || `user_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem('ai_toolkit_user_id', userId);
            
            let pdfChatHistory = [];
            let aiChatHistory = [];
            let currentPDFName = null;
            let activeTab = 'pdf_chat';

            let pdfStreamingBubble = null;
            let aiChatStreamingBubble = null;
            let socket, statusInterval, pingInterval;

            function setUIState(state, message = "") {
                ui.status.textContent = `Status: ${message}`;
                const isChatReady = state === 'ready_to_chat';
                const isWorkerReady = state === 'worker_ready' || isChatReady;
                
                ui.pdfUploadInput.disabled = !isWorkerReady;
                ui.uploadLabel.classList.toggle('bg-gray-500', !isWorkerReady);
                ui.uploadLabel.classList.toggle('bg-blue-500', isWorkerReady);
                ui.messageInput.disabled = !isChatReady;
                ui.sendButton.disabled = !isChatReady;

                ui.messageInputAI.disabled = !isWorkerReady;
                ui.sendButtonAI.disabled = !isWorkerReady;

                const canSavePDF = isChatReady && pdfChatHistory.length > 0;
                ui.saveChatButtonPDF.disabled = !canSavePDF;
                ui.saveChatButtonPDF.classList.toggle('opacity-50', !canSavePDF);
                ui.saveChatButtonPDF.classList.toggle('cursor-not-allowed', !canSavePDF);

                const canSaveAI = isWorkerReady && aiChatHistory.length > 0;
                ui.saveChatButtonAI.disabled = !canSaveAI;
                ui.saveChatButtonAI.classList.toggle('opacity-50', !canSaveAI);
                ui.saveChatButtonAI.classList.toggle('cursor-not-allowed', !canSaveAI);

                if (isChatReady) {
                    ui.messageInput.placeholder = "Ask a question about the PDF...";
                    ui.sendButton.classList.remove('bg-gray-500');
                    ui.sendButton.classList.add('bg-green-500');
                } else {
                    ui.messageInput.placeholder = message;
                    ui.sendButton.classList.add('bg-gray-500');
                    ui.sendButton.classList.remove('bg-green-500');
                }

                if (isWorkerReady) {
                    ui.messageInputAI.placeholder = "Send a message to the AI...";
                    ui.sendButtonAI.classList.remove('bg-gray-500');
                    ui.sendButtonAI.classList.add('bg-green-500');
                } else {
                    ui.messageInputAI.placeholder = message;
                    ui.sendButtonAI.classList.add('bg-gray-500');
                    ui.sendButtonAI.classList.remove('bg-green-500');
                }
            }

            async function checkWorkerStatus() {
                try {
                    const response = await fetch(`/status`);
                    if (!response.ok) throw new Error("Server not reachable");
                    const data = await response.json();
                    if (data.worker_connected) {
                        setUIState('worker_ready', 'AI worker connected. Ready to upload.');
                        clearInterval(statusInterval);
                        connectWebSocket();
                    } else {
                        setUIState('waiting_for_worker', 'Waiting for local AI worker...');
                    }
                } catch (error) {
                    setUIState('error', 'Could not connect to server.');
                }
            }

            function connectWebSocket() {
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${wsProtocol}//${window.location.host}/ws/web/${userId}`;
                socket = new WebSocket(wsUrl);
                socket.onopen = () => {
                    console.log("WebSocket connected successfully.");
                    if (pingInterval) clearInterval(pingInterval);
                    pingInterval = setInterval(() => {
                        if (socket && socket.readyState === WebSocket.OPEN) {
                            socket.send(JSON.stringify({ type: 'ping' }));
                        }
                    }, 20000);
                };
                socket.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        handleServerMessage(message);
                    } catch (error) {
                        console.error("Failed to handle message:", error);
                    }
                };
                socket.onclose = () => {
                    console.log("WebSocket disconnected.");
                    clearInterval(pingInterval);
                    setUIState('disconnected', 'Disconnected. Trying to reconnect...');
                    if (statusInterval) clearInterval(statusInterval);
                    statusInterval = setInterval(checkWorkerStatus, 3000);
                };
                socket.onerror = (error) => console.error("WebSocket Error:", error);
            }

            function addCopyButtonsTo(containerElement) {
                const codeBlocks = containerElement.querySelectorAll('pre');
                codeBlocks.forEach(block => {
                    if (block.querySelector('.copy-button')) return; // Don't add a button if one already exists
                    const button = document.createElement('button');
                    button.className = 'copy-button';
                    button.textContent = 'Copy';
                    block.appendChild(button);
                    button.addEventListener('click', () => {
                        const code = block.querySelector('code').innerText;
                        navigator.clipboard.writeText(code).then(() => {
                            button.textContent = 'Copied!';
                            setTimeout(() => { button.textContent = 'Copy'; }, 2000);
                        });
                    });
                });
            }

            function handleServerMessage(message) {
                let targetBubble, targetContainer, stateToSet, statusMsg;

                if (message.target === 'ai_chat') {
                    targetBubble = aiChatStreamingBubble;
                    targetContainer = ui.chatContainerAI;
                    stateToSet = 'worker_ready';
                    statusMsg = 'AI worker connected.';
                } else {
                    targetBubble = pdfStreamingBubble;
                    targetContainer = ui.chatContainer;
                    stateToSet = 'ready_to_chat';
                    statusMsg = `Ready: ${currentPDFName}`;
                }

                switch (message.type) {
                    case 'status':
                        addMessage(message.data, 'ai', 'pdf_chat');
                        if (message.data.includes("Ready for questions")) {
                            setUIState('ready_to_chat', `Ready: ${currentPDFName}`);
                        }
                        break;
                    case 'answer_chunk':
                        if (!targetBubble) {
                            targetBubble = addMessage('', 'ai', message.target);
                            if (message.target === 'ai_chat') aiChatStreamingBubble = targetBubble;
                            else pdfStreamingBubble = targetBubble;
                        }
                        targetBubble.textContent += message.data;
                        targetContainer.scrollTop = targetContainer.scrollHeight;
                        break;
                    case 'answer_end':
                        let bubbleToEnd = message.target === 'ai_chat' ? aiChatStreamingBubble : pdfStreamingBubble;
                        if (bubbleToEnd) {
                            bubbleToEnd.innerHTML = marked.parse(bubbleToEnd.textContent);
                            addCopyButtonsTo(bubbleToEnd);
                        }
                        if (message.target === 'ai_chat') aiChatStreamingBubble = null;
                        else pdfStreamingBubble = null;
                        setUIState(stateToSet, statusMsg);
                        break;
                    case 'error':
                        const target = pdfStreamingBubble ? 'pdf_chat' : 'ai_chat';
                        addMessage(`Error: ${message.data}`, 'ai', target);
                        setUIState('worker_ready', 'Error. Please try again.');
                        pdfStreamingBubble = null;
                        aiChatStreamingBubble = null;
                        break;
                }
            }

            function addMessage(text, sender, target = 'pdf_chat') {
                const history = (target === 'ai_chat') ? aiChatHistory : pdfChatHistory;
                const container = (target === 'ai_chat') ? ui.chatContainerAI : ui.chatContainer;
                history.push({ sender, text });
                
                const bubble = document.createElement('div');
                bubble.classList.add('chat-bubble', 'p-3', 'rounded-lg', 'w-fit');
                if (sender === 'user') bubble.classList.add('user-bubble', 'self-end', 'ml-auto');
                else bubble.classList.add('ai-bubble', 'self-start', 'mr-auto');
                
                bubble.textContent = text;
                container.appendChild(bubble);
                container.scrollTop = container.scrollHeight;
                
                setUIState(ui.status.textContent.replace('Status: ', ''));
                return bubble;
            }

            function renderHistory(history, target = 'pdf_chat') {
                const container = (target === 'ai_chat') ? ui.chatContainerAI : ui.chatContainer;
                container.innerHTML = '';
                history.forEach(msg => {
                    const bubble = document.createElement('div');
                    bubble.classList.add('chat-bubble', 'p-3', 'rounded-lg', 'w-fit');
                    if (msg.sender === 'user') bubble.classList.add('user-bubble', 'self-end', 'ml-auto');
                    else bubble.classList.add('ai-bubble', 'self-start', 'mr-auto');
                    bubble.innerHTML = marked.parse(msg.text);
                    addCopyButtonsTo(bubble);
                    container.appendChild(bubble);
                });
                container.scrollTop = container.scrollHeight;
            }

            function saveChat() {
                const historyToSave = (activeTab === 'ai_chat') ? aiChatHistory : pdfChatHistory;
                if (historyToSave.length === 0) return;

                const firstUserMessage = historyToSave.find(m => m.sender === 'user')?.text || 'New Chat';
                const chatName = (activeTab === 'pdf_chat' && currentPDFName) 
                    ? `${currentPDFName.replace('.pdf', '')}` 
                    : firstUserMessage.substring(0, 30);
                
                const chatId = `chat_${Date.now()}`;
                const chatData = {
                    id: chatId, name: chatName, type: activeTab,
                    timestamp: new Date().toISOString(), history: historyToSave,
                    pdfName: (activeTab === 'pdf_chat') ? currentPDFName : null,
                };

                localStorage.setItem(chatId, JSON.stringify(chatData));
                addMessage('Chat saved!', 'system', activeTab);
                loadSavedChats();
            }

            function loadSavedChats() {
                ui.sidebarTitle.textContent = activeTab === 'pdf_chat' ? "Saved PDF Chats" : "Saved AI Chats";
                ui.savedChatsList.innerHTML = '';
                const chats = [];
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key.startsWith('chat_')) {
                        const chat = JSON.parse(localStorage.getItem(key));
                        if (chat.type === activeTab) chats.push(chat);
                    }
                }
                chats.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                if (chats.length === 0) {
                    ui.savedChatsList.innerHTML = '<p class="text-slate-400">No saved chats.</p>';
                } else {
                    chats.forEach(chat => {
                        const item = document.createElement('div');
                        item.className = 'p-2 bg-slate-700 rounded-md cursor-pointer hover:bg-slate-600 truncate flex justify-between items-center';
                        item.textContent = chat.name;
                        item.onclick = () => loadChat(chat.id);
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'text-red-400 hover:text-red-300 ml-2';
                        deleteBtn.innerHTML = '&times;';
                        deleteBtn.onclick = (e) => { e.stopPropagation(); if (confirm(`Delete "${chat.name}"?`)) { localStorage.removeItem(chat.id); loadSavedChats(); } };
                        item.appendChild(deleteBtn);
                        ui.savedChatsList.appendChild(item);
                    });
                }
            }

            function loadChat(chatId) {
                const chatData = JSON.parse(localStorage.getItem(chatId));
                if (!chatData) return;

                if (chatData.type === 'pdf_chat') {
                    pdfChatHistory = chatData.history;
                    currentPDFName = chatData.pdfName;
                    renderHistory(pdfChatHistory, 'pdf_chat');
                    ui.pdfTitle.textContent = currentPDFName || 'PDF Preview';
                    ui.pdfViewer.src = '';
                    setUIState('worker_ready', `Loaded chat for '${currentPDFName}'. Re-upload file to continue.`);
                    addMessage(`Please re-upload "${currentPDFName}" to continue this conversation.`, 'system', 'pdf_chat');
                } else {
                    aiChatHistory = chatData.history;
                    renderHistory(aiChatHistory, 'ai_chat');
                    setUIState('worker_ready', 'AI worker connected.');
                }
                ui.sidebar.classList.add('-translate-x-full');
            }

            function startNewChat() {
                if (activeTab === 'pdf_chat') {
                    pdfChatHistory = [];
                    currentPDFName = null;
                    ui.chatContainer.innerHTML = '';
                    ui.pdfTitle.textContent = 'PDF Preview';
                    ui.pdfViewer.src = '';
                } else {
                    aiChatHistory = [];
                    ui.chatContainerAI.innerHTML = '';
                }
                setUIState('worker_ready', 'AI worker connected.');
            }

            async function uploadPDF() {
                const file = ui.pdfUploadInput.files[0];
                if (!file) return;
                startNewChat(); // Start a new chat session on new upload
                currentPDFName = file.name;
                ui.pdfTitle.textContent = currentPDFName;
                ui.pdfViewer.src = URL.createObjectURL(file);
                setUIState('processing', `Processing '${file.name}'...`);
                addMessage(`Uploading and sending to worker...`, 'ai', 'pdf_chat');
                const formData = new FormData();
                formData.append('file', file);
                try {
                    const response = await fetch(`/upload/${userId}`, { method: 'POST', body: formData });
                    if (!response.ok) throw new Error((await response.json()).detail || 'Failed to start PDF processing.');
                } catch (error) {
                    addMessage(`Error: ${error.message}`, 'ai', 'pdf_chat');
                    setUIState('worker_ready', 'Upload failed.');
                }
            }

            function sendMessage() {
                const question = ui.messageInput.value.trim();
                if (!question || !socket || socket.readyState !== WebSocket.OPEN) return;
                addMessage(question, 'user', 'pdf_chat');
                socket.send(JSON.stringify({ type: 'ask', data: question }));
                ui.messageInput.value = '';
                setUIState('ai_thinking', 'AI is thinking...');
            }
            
            function sendMessageAIChat() {
                const question = ui.messageInputAI.value.trim();
                if (!question || !socket || socket.readyState !== WebSocket.OPEN) return;
                addMessage(question, 'user', 'ai_chat');
                socket.send(JSON.stringify({ type: 'general_chat', data: question }));
                ui.messageInputAI.value = '';
                setUIState('ai_thinking', 'AI is thinking...');
            }

            ui.tabChatPDF.addEventListener('click', () => {
                activeTab = 'pdf_chat';
                ui.viewChatPDF.style.display = 'grid';
                ui.viewAIChat.style.display = 'none';
                ui.tabChatPDF.classList.add('active');
                ui.tabAIChat.classList.remove('active');
            });
            ui.tabAIChat.addEventListener('click', () => {
                activeTab = 'ai_chat';
                ui.viewChatPDF.style.display = 'none';
                ui.viewAIChat.style.display = 'flex';
                ui.tabChatPDF.classList.remove('active');
                ui.tabAIChat.classList.add('active');
            });

            ui.openSidebarButton.addEventListener('click', () => {
                loadSavedChats();
                ui.sidebar.classList.remove('-translate-x-full');
            });
            ui.closeSidebarButton.addEventListener('click', () => ui.sidebar.classList.add('-translate-x-full'));
            ui.newChatButton.addEventListener('click', () => {
                startNewChat();
                ui.sidebar.classList.add('-translate-x-full');
            });
            
            ui.pdfUploadInput.addEventListener('change', uploadPDF);
            ui.sendButton.addEventListener('click', sendMessage);
            ui.messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !ui.messageInput.disabled) sendMessage(); });
            ui.saveChatButtonPDF.addEventListener('click', saveChat);
            
            ui.sendButtonAI.addEventListener('click', sendMessageAIChat);
            ui.messageInputAI.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !ui.messageInputAI.disabled) sendMessageAIChat(); });
            ui.saveChatButtonAI.addEventListener('click', saveChat);
            
            statusInterval = setInterval(checkWorkerStatus, 3000);
            checkWorkerStatus();
            ui.tabChatPDF.click();
        });
    </script>
</body>
</html>
