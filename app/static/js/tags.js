// static/js/tags.js

(function () {
    // --- Tag Management: Rename/Delete Modals (for tag management page) ---
    function setupTagModals() {
        // Rename modal
        const renameForm = document.getElementById('renameTagForm');
        if (renameForm) {
            document.querySelectorAll('.btn-rename').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.getElementById('renameTagId').value = btn.dataset.tagId;
                    document.getElementById('newTagName').value = btn.dataset.tagName;
                    openModal('renameTagModal');
                });
            });
            renameForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const tagId = document.getElementById('renameTagId').value;
                const newName = document.getElementById('newTagName').value.trim();
                const msg = document.getElementById('renameTagMsg');
                msg.textContent = '';
                const res = await fetch(`/tags/rename/${tagId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': window.csrf_token },
                    body: JSON.stringify({ new_name: newName })
                });
                const data = await res.json();
                if (data.success) {
                    document.querySelector(`.btn-rename[data-tag-id="${tagId}"]`).closest('.tag-pill').childNodes[0].textContent = newName + " ";
                    closeModal('renameTagModal');
                } else {
                    msg.textContent = data.error || "Rename failed";
                }
            });
        }

        // Delete modal
        const deleteForm = document.getElementById('deleteTagForm');
        if (deleteForm) {
            document.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.getElementById('deleteTagId').value = btn.dataset.tagId;
                    document.getElementById('deleteTagConfirm').textContent = `Are you sure you want to delete tag "${btn.dataset.tagName}"? This cannot be undone.`;
                    openModal('deleteTagModal');
                });
            });
            deleteForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const tagId = document.getElementById('deleteTagId').value;
                const msg = document.getElementById('deleteTagMsg');
                msg.textContent = '';
                const res = await fetch(`/tags/delete/${tagId}`, {
                    method: 'POST',
                    headers: { 'Accept': 'application/json', 'X-CSRFToken': window.csrf_token }
                });
                const data = await res.json();
                if (data.success) {
                    document.querySelector(`.btn-delete[data-tag-id="${tagId}"]`).closest('.tag-list-item').remove();
                    closeModal('deleteTagModal');
                } else {
                    msg.textContent = data.error || "Delete failed";
                }
            });
        }

        // Modal utils
        function openModal(id) {
            const m = document.getElementById(id);
            if (!m) return;
            m.style.display = 'block';
            m.setAttribute('aria-hidden', 'false');
            const focusTarget = m.querySelector('input, button');
            if (focusTarget) focusTarget.focus();
        }
        function closeModal(id) {
            const m = document.getElementById(id);
            if (!m) return;
            m.style.display = 'none';
            m.setAttribute('aria-hidden', 'true');
        }
        document.querySelectorAll('.close-modal').forEach(btn => btn.addEventListener('click', e => {
            closeModal(btn.closest('.modal').id);
        }));
        document.addEventListener('keydown', e => {
            if (e.key === "Escape") Array.from(document.querySelectorAll('.modal')).forEach(m => closeModal(m.id));
        });
    }

    // --- Helper: If input is in last message, scroll container so input/suggestions are visible ---
    function scrollTagInputIntoView(input) {
        const msgDiv = input.closest('[data-msg-id]');
        if (!msgDiv) return;
        // Find the chat body container (uses id="body" on both chat and conversation pages)
        const chatBody = document.getElementById('body');
        // Only scroll if this is the last message
        if (chatBody && msgDiv === chatBody.lastElementChild) {
            // Scroll so the input is visible (and allow for suggestions dropdown)
            msgDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
            // Ensure a bit of padding at the bottom for dropdown
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight + 100;
            }, 120);
        }
    }

    // --- Tag Add/Remove/Autocomplete (for chat/conversation pages) ---
    function setupTagInputs() {
        // Skip if no tag-inputs or tag buttons exist on page
        if (!document.querySelector('.tag-input') && !document.querySelector('.add-tag-btn')) return;

        // Add Tag
        document.addEventListener('click', function (e) {
            if (e.target.classList.contains('add-tag-btn')) {
                const container = e.target.closest('.tag-list');
                const input = container?.parentElement.querySelector('.tag-input');
                if (input) {
                    input.style.display = 'inline-block';
                    input.focus();
                    scrollTagInputIntoView(input); // <<<--- PATCH: Scroll last message input into view
                }
            }
            // Remove Tag
            if (e.target.classList.contains('remove-tag')) {
                const tagSpan = e.target.closest('.tag-pill');
                const tagId = tagSpan.dataset.tagId;
                const msgDiv = tagSpan.closest('[data-msg-id]');
                const msgId = msgDiv.dataset.msgId;
                fetch(`/messages/${msgId}/tags/${tagId}`, {
                    method: 'DELETE',
                    headers: { 'X-CSRF-Token': window.csrf_token }
                }).then(() => tagSpan.remove());
            }
        });

        // Helper: Add tag to message (reuse)
        async function addTagToMessage(msgDiv, tagName, input, suggestionsDiv) {
            const msgId = msgDiv.dataset.msgId;
            const resp = await fetch(`/messages/${msgId}/tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.csrf_token },
                body: JSON.stringify({ tag: tagName })
            });
            if (resp.ok) {
                const data = await resp.json();
                const tagList = msgDiv.querySelector('.tag-list');
                const span = document.createElement('span');
                span.className = 'tag-pill';
                span.dataset.tagId = data.tag.id;
                span.innerHTML = `${data.tag.name}<span class="remove-tag" title="Remove tag">&times;</span>`;
                const addBtn = tagList.querySelector('.add-tag-btn');
                tagList.insertBefore(span, addBtn);
                if (input) input.value = '';
                if (suggestionsDiv) {
                    suggestionsDiv.innerHTML = '';
                    suggestionsDiv.style.display = 'none';
                }
            } else {
                // Optionally show toast/error
            }
        }

        // Helper: Bind autocomplete to tag-input
        function bindTagInput(input) {
            const msgDiv = input.closest('[data-msg-id]');
            const suggestionsDiv = msgDiv.querySelector('.tag-suggestions');
            let suggestionIdx = -1;

            function highlightSuggestion(idx) {
                const suggestions = suggestionsDiv.querySelectorAll('.tag-suggestion-item');
                suggestions.forEach((item, i) => {
                    item.classList.toggle('active', i === idx);
                });
            }

            input.addEventListener('input', async function () {
                const q = input.value;
                suggestionIdx = -1;
                if (!q) {
                    suggestionsDiv.style.display = 'none';
                    suggestionsDiv.innerHTML = '';
                    return;
                }
                const resp = await fetch(`/tags/?q=${encodeURIComponent(q)}`);
                const tags = await resp.json();
                suggestionsDiv.innerHTML = '';
                if (tags.length === 0) {
                    suggestionsDiv.style.display = 'none';
                    return;
                }
                tags.forEach((tag, idx) => {
                    const item = document.createElement('div');
                    item.className = 'tag-suggestion-item';
                    item.textContent = tag.name;
                    item.tabIndex = -1;
                    item.addEventListener('mousedown', async (e) => {
                        e.preventDefault();
                        await addTagToMessage(msgDiv, tag.name, input, suggestionsDiv);
                    });
                    suggestionsDiv.appendChild(item);
                });
                suggestionsDiv.style.display = 'block';
                // PATCH: scroll again when suggestions show up (last message only)
                scrollTagInputIntoView(input);
            });

            input.addEventListener('keydown', async function (e) {
                const suggestions = suggestionsDiv.querySelectorAll('.tag-suggestion-item');
                if ((e.key === 'ArrowDown' || e.key === 'Tab') && suggestions.length > 0) {
                    e.preventDefault();
                    suggestionIdx = (suggestionIdx + 1) % suggestions.length;
                    highlightSuggestion(suggestionIdx);
                    input.value = suggestions[suggestionIdx].textContent;
                } else if (e.key === 'ArrowUp' && suggestions.length > 0) {
                    e.preventDefault();
                    suggestionIdx = (suggestionIdx - 1 + suggestions.length) % suggestions.length;
                    highlightSuggestion(suggestionIdx);
                    input.value = suggestions[suggestionIdx].textContent;
                } else if (e.key === 'Enter') {
                    if (suggestionIdx >= 0 && suggestions[suggestionIdx]) {
                        e.preventDefault();
                        await addTagToMessage(msgDiv, suggestions[suggestionIdx].textContent, input, suggestionsDiv);
                        suggestionIdx = -1;
                    } else if (input.value.trim()) {
                        e.preventDefault();
                        await addTagToMessage(msgDiv, input.value.trim(), input, suggestionsDiv);
                        suggestionIdx = -1;
                    }
                } else if (e.key === 'Escape') {
                    // Hide and clear suggestions
                    suggestionsDiv.style.display = 'none';
                    suggestionsDiv.innerHTML = '';
                    suggestionIdx = -1;
                    input.value = '';
                    // Hide and blur the input
                    input.style.display = 'none';
                    input.blur();
                }
            });
            input.addEventListener('blur', () => {
                setTimeout(() => {
                    input.value = '';
                    input.style.display = 'none';
                    suggestionsDiv.style.display = 'none';
                    suggestionsDiv.innerHTML = '';
                }, 100);
            });
        }

        // Setup tag-inputs on page load
        document.querySelectorAll('.tag-input').forEach(bindTagInput);
    }

    // --- Main Entry Point ---
    document.addEventListener('DOMContentLoaded', function () {
        setupTagModals();
        setupTagInputs();
    });
})();
