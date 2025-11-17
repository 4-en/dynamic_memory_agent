const settingsModal = document.getElementById('settings-modal');
const settingsToggle = document.getElementById('settings-toggle');
const infoToggle = document.getElementById('info-toggle');
const infoModal = document.getElementById('info-modal');

settingsToggle.addEventListener('click', () => {
    settingsModal.showModal();

});

infoToggle.addEventListener('click', () => {
    infoModal.showModal();
});

// close modals when clicking backdrop
settingsModal.addEventListener('click', (e) => {
    const rect = settingsModal.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
        settingsModal.close();
    }
});

infoModal.addEventListener('click', (e) => {
    const rect = infoModal.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
        infoModal.close();
    }
});



function add_settings_toggle(key, label, default_value, hover_text, on_change) {
    // create a toggle using this template:
    /*
        <label class="switch">
            <input type="checkbox">
            <span class="slider"></span>
        </label>
    */
    // also use local storage to save/load the value
    let start_value = localStorage.getItem(key) ?? default_value ?? false;





    const container = document.getElementById('settings-container');

    const label_elem = document.createElement('label');
    label_elem.className = 'switch';

    const input_elem = document.createElement('input');
    input_elem.type = 'checkbox';
    input_elem.checked = (start_value === 'true' || start_value === true);



    const slider_elem = document.createElement('span');
    slider_elem.className = 'slider';

    label_elem.appendChild(input_elem);
    label_elem.appendChild(slider_elem);

    const setting_container = document.createElement('div');
    setting_container.className = 'setting-item';

    const text_label = document.createElement('span');
    text_label.innerText = label;
    if (hover_text) {
        text_label.title = hover_text;
    }

    setting_container.appendChild(text_label);
    setting_container.appendChild(label_elem);

    container.appendChild(setting_container);

    input_elem.addEventListener('change', () => {
        localStorage.setItem(key, input_elem.checked);
        if (on_change) {
            on_change(input_elem.checked, setting_container);
        }
    });

    // fire on_change initially to set the correct state
    if (on_change) {
        on_change(start_value === 'true' || start_value === true, setting_container);
    }

    return setting_container;

}

function add_setting_divider(section_name='') {
    const container = document.getElementById('settings-container');

    const divider = document.createElement('hr');
    divider.className = 'setting-divider';

    if (section_name) {
        const section_label = document.createElement('span');
        section_label.className = 'setting-section-label';
        section_label.innerText = section_name;
        container.appendChild(section_label);
    }

    container.appendChild(divider);
}

function add_settings_button(label, hover_text, button_text, on_click) {
    const container = document.getElementById('settings-container');

    const button = document.createElement('button');
    button.className = 'settings-button';
    button.innerText = button_text;
    if (hover_text) {
        button.title = hover_text;
    }

    button.addEventListener('click', () => {
        if (on_click) {
            on_click();
        }
    });

    const text_label = document.createElement('span');
    text_label.innerText = label;
    if (hover_text) {
        text_label.title = hover_text;
    }

    const setting_container = document.createElement('div');
    setting_container.className = 'setting-item';

    setting_container.appendChild(text_label);
    setting_container.appendChild(button);

    container.appendChild(setting_container);

    return button;
}

function toggle_hide_message_type(message_type, hide) {
    const multiMessageList = document.getElementById('multi-message-list');
    if (hide) {
        multiMessageList.classList.add(`hide-${message_type}`);
    } else {
        multiMessageList.classList.remove(`hide-${message_type}`);
    }
}

window.addEventListener('load', () => {
    
    // toggle multi response mode (display responses from multiple models side by side)
    add_settings_toggle(
        'multi_response_mode',
        'Enable Multi-Response Mode',
        false,
        'Display responses from multiple models side by side in the chat',
        (enabled) => {
            const multiMessageList = document.getElementById('multi-message-list');
            if (enabled) {
                multiMessageList.classList.add('multi-response-mode');
                llm_mode = 'compare';
            } else {
                multiMessageList.classList.remove('multi-response-mode');
                llm_mode = 'default';
            }
        }
    );

    const darkModeToggle = add_settings_toggle(
        'dark_mode',
        'Enable Dark Mode',
        true,
        'Toggle dark mode for the interface',
        (enabled, container) => {
            const isDarkMode = enabled;
            if (isDarkMode) {
                document.documentElement.classList.add('dark-mode');
            } else {
                document.documentElement.classList.remove('dark-mode');
            }
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
            // also update the button state in case it is out of sync
            const container_button = container.querySelector('input[type="checkbox"]');
            if (container_button) {
                container_button.checked = isDarkMode;
            }

        }
    );

    // add function that automatically syncs the toggle with the current theme,
    // based on class list changes to the document element
    const observer = new MutationObserver(() => {
        const isDarkMode = document.documentElement.classList.contains('dark-mode');
        const container_button = darkModeToggle.querySelector('input[type="checkbox"]');
        if (container_button) {
            container_button.checked = isDarkMode;
        }
    });

    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });


    // Message type visibility toggles

    add_setting_divider('Message Types');

    add_settings_toggle(
        'hide_thoughts',
        'Hide Reasoning',
        false,
        'Toggle visibility of assistant reasoning in the chat',
        (enabled) => {
            toggle_hide_message_type('thoughts', enabled);
        }
    );

    add_settings_toggle(
        'hide_queries',
        'Hide Queries',
        false,
        'Toggle visibility of memory queries in the chat',
        (enabled) => {
            toggle_hide_message_type('queries', enabled);
        }
    );

    add_settings_toggle(
        'hide_retrievals',
        'Hide Retrievals',
        false,
        'Toggle visibility of memory retrievals in the chat',
        (enabled) => {
            toggle_hide_message_type('retrievals', enabled);
        }
    );

    add_settings_toggle(
        'hide_summaries',
        'Hide Summaries',
        false,
        'Toggle visibility of memory summaries in the chat',
        (enabled) => {
            toggle_hide_message_type('summaries', enabled);
        }
    );

    add_settings_toggle(
        'hide_status',
        'Hide Status Messages',
        false,
        'Toggle visibility of status messages in the chat',
        (enabled) => {
            toggle_hide_message_type('status', enabled);
        }
    );

    add_settings_toggle(
        'hide_feedback',
        'Hide Self-Feedback Info',
        false,
        'Toggle visibility of self-feedback info messages in the chat',
        (enabled) => {
            toggle_hide_message_type('info', enabled);
        }
    );

    // Button to clear all messages, local and server-side
    add_setting_divider();

    add_settings_button(
        'Clear All Messages',
        'Clear all chat messages from local storage and the server',
        'Clear Messages',
        () => {
            if (confirm('Are you sure you want to clear all messages? This action cannot be undone.')) {
                const token = localStorage.getItem('user_token');
                if (!token) {
                    alert('No user token found. Cannot clear messages on server.');
                    return;
                }
                // Clear local storage
                localStorage.removeItem('chat_messages');
                // Send request to server to clear messages
                fetch('/api/clear_history', { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ user_token: token })
                })

                    .then(response => {
                        if (response.ok) {
                            // Reload the page to reflect changes
                            localStorage.removeItem('user_token');
                            window.location.reload();
                        } else {
                            alert('Failed to clear messages on the server.');
                        }
                    })
                    .catch(error => {
                        console.error('Error clearing messages:', error);
                        alert('An error occurred while clearing messages.');
                    });
            }
        }
    );
});