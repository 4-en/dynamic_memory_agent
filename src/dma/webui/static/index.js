const themeToggle = document.getElementById('theme-toggle');
const messageList = document.getElementById('message-list');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
var converter = null;

// Initialize the markdown converter
window.addEventListener('load', () => {
    converter = new showdown.Converter();
});

themeToggle.addEventListener('click', (event) => {
    event.preventDefault();
    const isDarkMode = document.documentElement.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
});

/**
 * Adds a new message to the chat interface.
 * @param {string} role - 'user' or 'assistant'
 * @param {string} type - 'thought' or 'response' for the assistant
 * @param {string} content - The text content of the message
 * @returns {HTMLElement} The newly created message element
 */
function addMessage(role, type, content) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${role}-message`, `${type}-message`);
    messageElement.textContent = content; // FIX: Use textContent to preserve whitespace
    messageList.appendChild(messageElement);
    messageList.scrollTop = messageList.scrollHeight;
    return messageElement;
}

// --- Event 1: Load History on Page Load ---
window.addEventListener('load', async () => {
    if (!converter) {
        // give small grace period for converter to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    try {
        const response = await fetch('/api/history');
        if (!response.ok) throw new Error('Failed to fetch history');
        const history = await response.json();
        history.forEach(msg => {
            const el = addMessage(msg.role, 'response', msg.content);
            if (converter) {
                const htmlContent = converter.makeHtml(msg.content);
                el.innerHTML = htmlContent;
            }
        });
    } catch (error) {
        console.error('Error fetching history:', error);
        addMessage('assistant', 'response', 'Sorry, I couldn\'t load the chat history.');
    }
});

// --- Event 2: Handle Form Submission ---
chatForm.addEventListener('submit', async (event) => {

    event.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    addMessage('user', 'response', message);
    messageInput.value = '';
    messageInput.disabled = true;
    chatForm.querySelector('#send-button').disabled = true;

    try {

        // replace send button with loading indicator
        const loadingIndicator = document.createElement('span');
        loadingIndicator.classList.add('loader');
        chatForm.querySelector('#send-button').replaceWith(loadingIndicator);

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = '';
        let currentType = null;
        let responseElement = null;
        let currentResponseRaw = null;


        let not_done = true;
        while (not_done) {
            const { value, done } = await reader.read();
            if (done && !value) break;
            not_done = !done;

            buffer += decoder.decode(value, { stream: true });

            // --- START OF FIX ---
            // Add an inner loop to process all complete JSON objects in the buffer
            let processing = true;
            while (processing) {
                // Find the first JSON object
                let startIdx = buffer.indexOf('{');
                if (startIdx === -1) {
                    processing = false; // No start brace, wait for more data
                    continue;
                }

                // Find the matching end brace
                let endIdx = startIdx + 1;
                let braceCount = 1;
                while (endIdx < buffer.length) {
                    if (buffer[endIdx] === '{') braceCount++;
                    else if (buffer[endIdx] === '}') braceCount--;
                    if (braceCount === 0) break;
                    endIdx++;
                }

                if (braceCount !== 0) {
                    processing = false; // Incomplete object, wait for more data
                    continue;
                }

                // --- Found a complete object ---
                const jsonString = buffer.slice(startIdx, endIdx + 1);
                buffer = buffer.slice(endIdx + 1); // Update buffer for next iteration

                let chunk;
                try {
                    chunk = JSON.parse(jsonString);
                } catch (e) {
                    console.error('Failed to parse JSON chunk:', jsonString, e);
                    continue; // Skip this malformed chunk
                }

                // (Your existing logic for appending the message)
                if (currentType !== null && responseElement !== null && chunk.type === currentType) {
                    // append to existing message
                    const content = chunk.content;
                    currentResponseRaw += content;

                    if (converter) {
                        // Convert markdown to HTML
                        const htmlContent = converter.makeHtml(currentResponseRaw);
                        responseElement.innerHTML = htmlContent;
                    } else {
                        responseElement.textContent = currentResponseRaw;
                    }
                } else {
                    // new message
                    let role = "assistant";
                    if (chunk.type === 'info' || chunk.type === 'error') {
                        role = 'info';
                    }
                    console.log("Adding chunk:", chunk.content);
                    responseElement = addMessage(role, chunk.type, chunk.content);
                    currentResponseRaw = chunk.content;

                    if (converter) {
                        // Convert markdown to HTML
                        const htmlContent = converter.makeHtml(currentResponseRaw);
                        responseElement.innerHTML = htmlContent;
                    }

                    currentType = chunk.type;
                }

                messageList.scrollTop = messageList.scrollHeight;

            } // --- END OF INNER processing LOOP ---
        } // --- END OF OUTER not_done LOOP ---

    } catch (error) {
        console.error('Error during chat:', error);
        addMessage('assistant', 'response', 'Sorry, an error occurred. Please try again.');
    } finally {
        // restore send button
        const sendButton = document.createElement('button');
        sendButton.id = 'send-button';
        sendButton.type = 'submit';
        sendButton.textContent = 'Send';
        chatForm.querySelector('.loader').replaceWith(sendButton);
        messageInput.disabled = false;
        chatForm.querySelector('#send-button').disabled = false;
        messageInput.focus();
    }
});