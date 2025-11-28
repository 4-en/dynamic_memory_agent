const themeToggle = document.getElementById('theme-toggle');
const messageList = document.getElementById('message-list');
const messageListAlt1 = document.getElementById('message-list-2');
const messageListAlt2 = document.getElementById('message-list-3');
const messageListAlt1Label = document.getElementById('model-label-2');
const messageListAlt2Label = document.getElementById('model-label-3');
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
    localStorage.setItem('dark_mode', isDarkMode ? 'true' : 'false');
});

/**
 * Adds a new message to the chat interface.
 * @param {string} role - 'user' or 'assistant'
 * @param {string} type - 'thought' or 'response' for the assistant
 * @param {string} content - The text content of the message
 * @returns {HTMLElement} The newly created message element
 */
function addMessage(role, type, content, source='default') {
    let m_list = messageList;
    if (source !== 'default') {
        const parts = source.split(':');
        if (parts.length === 2) {
            const index = parseInt(parts[0]);
            list_name = parts[1];
            if (index === 1) {
                m_list = messageListAlt1;
                messageListAlt1Label.innerText = list_name;
            } else if (index === 2) {
                m_list = messageListAlt2;
                messageListAlt2Label.innerText = list_name;
            }
            
        }
    }
    // get the status message if it exists
    const existingStatus = m_list.querySelector('.status-message');
    if (existingStatus) {
        existingStatus.remove();
    }
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${role}-message`, `${type}-message`);
    messageElement.textContent = content; // FIX: Use textContent to preserve whitespace
    m_list.appendChild(messageElement);

    // re-add the status message if it existed
    if (existingStatus) {
        m_list.appendChild(existingStatus);
    }
    m_list.scrollTop = m_list.scrollHeight;
    return messageElement;
}

function get_token() {
    // returns a random unique token that is used to identify a user session
    // store in local storage and create if not exists
    let token = localStorage.getItem('user_token');
    if (!token) {
        token = crypto.randomUUID();
        localStorage.setItem('user_token', token);
    }
    return token;
}

// --- Event 1: Load History on Page Load ---
window.addEventListener('load', async () => {
    if (!converter) {
        // give small grace period for converter to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    try {
        const response = await fetch('/api/history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_token: get_token() }),
        });
        if (!response.ok) throw new Error('Failed to fetch history');
        const history = await response.json();
        history.forEach(msg => {
            const el = addMessage(msg.role, 'response', msg.content);
            if (converter) {
                const htmlContent = converter.makeHtml(msg.content);
                el.innerHTML = htmlContent;
                MathJax.typesetPromise([el]).catch((err) => console.error('MathJax typeset failed: ', err));
            }
        });
    } catch (error) {
        console.error('Error fetching history:', error);
        addMessage('assistant', 'response', 'Sorry, I couldn\'t load the chat history.');
    }
});
var _last_status_update = 0;
const STATUS_UPDATE_INTERVAL = 1000; // milliseconds
var status_queue = [];
async function process_status_queue() {
    while (status_queue.length > 0) {
        // wait for enough time to pass
        const now = Date.now();
        let time_since_last = now - _last_status_update;
        if (time_since_last < STATUS_UPDATE_INTERVAL) {
            // wait the remaining time
            const wait_time = STATUS_UPDATE_INTERVAL - time_since_last;
            await new Promise(resolve => setTimeout(resolve, wait_time));
        }
        const item = status_queue.shift();
        item.element.textContent = item.status;
        _last_status_update = Date.now();
    }
}
function update_status_message(element, new_status) {

    // if the status is the same as current, do nothing
    if (element.textContent === new_status) {
        return;
    }

    // if the status is already in the queue, also do nothing
    for (const item of status_queue) {
        if (item.element === element && item.status === new_status) {
            return;
        }
    }

    // change the status message text if enough time has passed, otherwise add to a queue
    const now = Date.now();
    if (now - _last_status_update > STATUS_UPDATE_INTERVAL) {
        element.textContent = new_status;
        _last_status_update = now;
    } else {
        status_queue.push({ element: element, status: new_status });
        if (status_queue.length === 1) {
            // start processing the queue
            process_status_queue();
        }
    }
}

// --- Event 2: Handle Form Submission ---
var llm_mode = 'default';
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
        const sendButton = chatForm.querySelector('#send-button');
        // hide send button without removing to preserve event listeners
        sendButton.parentNode.appendChild(loadingIndicator);
        sendButton.style.display = 'none';

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, user_token: get_token(), mode: llm_mode })
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = '';
        let currentType = null;
        let responseElement = null;
        let currentResponseRaw = null;
        let currentSource = null;

        const statusMessage = addMessage('assistant', 'status', 'Thinking...');


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
                let in_quotes = false;
                let quote_char = '';
                while (endIdx < buffer.length) {

                    // Handle string literals to avoid counting braces inside strings
                    if (in_quotes) {
                        if (buffer[endIdx] === quote_char && buffer[endIdx - 1] !== '\\') {
                            in_quotes = false;
                            quote_char = '';
                        }
                        endIdx++;
                        continue;
                    } else {
                        if (buffer[endIdx] === '"' || buffer[endIdx] === "'") {
                            in_quotes = true;
                            quote_char = buffer[endIdx];
                            endIdx++;
                            continue;
                        }
                    }

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

                if (chunk.status) {
                    // handle status updates
                    update_status_message(statusMessage, chunk.status);
                }

                if (!chunk.content || chunk.content.length === 0) {
                    continue; // skip if no content
                }

                // (Your existing logic for appending the message)
                if (currentType !== null && responseElement !== null && chunk.type === currentType && chunk.source === currentSource) {
                    // append to existing message
                    const content = chunk.content;
                    currentResponseRaw += content;

                    if (converter) {
                        // Convert markdown to HTML
                        const htmlContent = converter.makeHtml(currentResponseRaw);
                        responseElement.innerHTML = htmlContent;
                        MathJax.typesetPromise([responseElement]).catch((err) => console.error('MathJax typeset failed: ', err));
                    } else {
                        responseElement.textContent = currentResponseRaw;
                    }
                } else {
                    // new message
                    let role = "assistant";
                    if (chunk.type === 'info' || chunk.type === 'error') {
                        role = 'info';
                    }
                    const source = chunk.source ? chunk.source : 'default';
                    currentSource = source;
                    console.log("Adding chunk:", chunk.content);
                    responseElement = addMessage(role, chunk.type, chunk.content, source);
                    currentResponseRaw = chunk.content;

                    if (converter) {
                        // Convert markdown to HTML
                        const htmlContent = converter.makeHtml(currentResponseRaw);
                        responseElement.innerHTML = htmlContent;
                        MathJax.typesetPromise([responseElement]).catch((err) => console.error('MathJax typeset failed: ', err));
                    }

                    currentType = chunk.type;

                }

                messageList.scrollTop = messageList.scrollHeight;

            } // --- END OF INNER processing LOOP ---
        } // --- END OF OUTER not_done LOOP ---

        // remove status message
        statusMessage.remove();

    } catch (error) {
        console.error('Error during chat:', error);
        addMessage('assistant', 'response', 'Sorry, an error occurred. Please try again.');
    } finally {
        // restore send button
        const sendButton = chatForm.querySelector('#send-button');
        sendButton.style.display = 'inline-block';
        sendButton.disabled = false;
        //sendButton.id = 'send-button';
        //sendButton.type = 'submit';
        //sendButton.textContent = 'Send';
        chatForm.querySelector('.loader').remove();
        messageInput.disabled = false;
        messageInput.focus();
    }
});