const themeToggle = document.getElementById('theme-toggle');
const messageList = document.getElementById('message-list');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const answerSelections = document.getElementById('answer-selections');
const answerContainer = document.querySelector('.answer-container');
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
function addMessage(role, type, content) {
    let m_list = messageList;
    // get the status message if it exists
    const existingStatus = m_list.querySelector('.status-message');
    if (existingStatus) {
        existingStatus.remove();
    }
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${role}-message`, `${type}-message`);
    
    const htmlContent = converter.makeHtml(content);
    messageElement.innerHTML = htmlContent;
    MathJax.typesetPromise([messageElement]).catch((err) => console.log('MathJax typeset failed: ' + err.message));

    m_list.appendChild(messageElement);

    // re-add the status message if it existed
    if (existingStatus) {
        m_list.appendChild(existingStatus);
    }
    m_list.scrollTop = m_list.scrollHeight;
    return messageElement;
}

// for blind test, generate a new token each page refresh
const TOKEN = crypto.randomUUID();
function get_token() {
    return TOKEN;
}
var answer_sent = false;
function send_blind_test_rating(best_model_id) {
    if (answer_sent) return; // prevent multiple submissions
    answer_sent = true;

    answerContainer.classList.add('hidden-answer');
    chatForm.classList.remove('hidden-answer');
    fetch('/api/rate_blind_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_token: get_token(), best_model_id: best_model_id })
    })
    .then(response => response.json())
    .then(data => {
        // add the response message to the message list
        addMessage('assistant', 'response', data.content);
    });
}

function add_answer_to_selections(model_id, message_content) {
    // creates a new element in the answer selections area containing the message content and event listener for selection

    const messageElement = document.createElement('div');
    messageElement.classList.add('select-answer-message');
    messageElement.innerHTML = converter.makeHtml(message_content);
    MathJax.typesetPromise([messageElement]).catch((err) => console.log('MathJax typeset failed: ' + err.message));


    // wrap in outer div
    const outerDiv = document.createElement('div');
    outerDiv.appendChild(messageElement);

    outerDiv.addEventListener('click', () => {
        send_blind_test_rating(model_id);
    });

    answerSelections.appendChild(outerDiv);
}

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

        const response = await fetch('/api/blind_test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, user_token: get_token()})
        });

        if (!response.ok) throw new Error('Network response was not ok');

        // convert to object
        const result = await response.json();
        // result should have 'answers' field with list of answers from different models
        // each answer should have 'model_id' and 'message' fields
        const answers = result.answers;

        // clear old answer selections
        answerSelections.innerHTML = '';

        // add each answer to the selections area
        answers.forEach(answer => {
            add_answer_to_selections(answer.model_id, answer.content);
        });

        answer_sent = false; // allow answer submission again
        answerContainer.classList.remove('hidden-answer');
        chatForm.classList.add('hidden-answer');
        

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