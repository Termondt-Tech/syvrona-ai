(function () {
    // --- Helper: If input is in last message, scroll container so input/suggestions are visible ---
    function scrollTagInputIntoView(input) {
        const msgDiv = input.closest('[data-msg-id]');
        if (!msgDiv) return;
        const chatBody = document.getElementById('body');
        if (chatBody && msgDiv === chatBody.lastElementChild) {
            msgDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight + 100;
            }, 120);
        }
    }

    // --- Helper: Add tag to message (used everywhere) ---
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
        }
    }

    // --- Bind autocomplete and events to a single tag-input (for chat/convo only) ---
    function bindTagInput(input) {
        if (!input) return;
        // Remove previous listeners by replacing the element (vanilla JS "clone hack" to avoid double-binding)
        const oldInput = input;
        const newInput = input.cloneNode(true);
        oldInput.parentNode.replaceChild(newInput, oldInput);
        input = newInput;

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
                suggestionsDiv.style.display = 'none';
                suggestionsDiv.innerHTML = '';
                suggestionIdx = -1;
                input.value = '';
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

    // --- Setup tag functionality for all existing tag-inputs (chat/convo) ---
    function setupTagInputs() {
        // Always attach delegated handlers (works even if inputs appear later)
        document.addEventListener('click', function (e) {
            if (e.target.classList.contains('add-tag-btn')) {
                const msgDiv = e.target.closest('[data-msg-id]');
                const input = msgDiv && msgDiv.querySelector('.tag-input');
                if (input) {
                    input.style.display = 'inline-block';
                    input.focus();
                    scrollTagInputIntoView(input);
                }
            }
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

        // Only bind existing inputs present at load (if any)
        const inputs = document.querySelectorAll('.tag-input');
        if (inputs.length) inputs.forEach(bindTagInput);
    }


    // --- Setup modal logic for tag rename/delete (tags page) ---
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
                    headers: { 'Accept': 'application/json', 'X-CSRF-Token': window.csrf_token }
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

    // --- Main Entry Point ---
    document.addEventListener('DOMContentLoaded', function () {
        setupTagInputs();
        setupTagModals();
    });

    // --- Export bindTagInput globally for dynamic usage ---
    window.SyvronaTags = window.SyvronaTags || {};
    window.SyvronaTags.bindTagInput = bindTagInput;

})();
