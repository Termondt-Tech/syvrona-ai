// static/js/taginput.js

document.addEventListener("DOMContentLoaded", function () {
    const tagBar = document.getElementById("tag-bar");
    const tagInput = document.getElementById("tag-input");
    const tagSuggestions = document.getElementById("tag-suggestions");
    const tagIdsDiv = document.getElementById("tag-ids");

    if (tagInput) {
        tagInput.setAttribute('autocomplete', 'off');
        tagInput.setAttribute('autocorrect', 'off');
        tagInput.setAttribute('autocapitalize', 'off');
        tagInput.setAttribute('spellcheck', 'false');
    }
    // Exit if not present (so safe to include everywhere)
    if (!tagBar || !tagInput || !tagSuggestions || !tagIdsDiv) return;

    let currentTags = Array.from(tagBar.querySelectorAll('.tag-pill')).map(
        span => ({ id: span.dataset.tagId, name: span.textContent.trim() })
    );

    function renderTagIds() {
        tagIdsDiv.innerHTML = '';
        currentTags.forEach(tag => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'tag_ids[]';
            input.value = tag.id;
            tagIdsDiv.appendChild(input);
        });
    }

    // Remove tag (event delegation)
    tagBar.addEventListener('click', function (e) {
        if (e.target.classList.contains('remove-tag')) {
            const tagPill = e.target.closest('.tag-pill');
            tagPill.remove();
            currentTags = currentTags.filter(tag => tag.id !== tagPill.dataset.tagId);
            renderTagIds();
        }
    });

    // Autocomplete
    tagInput.addEventListener('input', async function () {
        const q = tagInput.value.trim();
        if (!q) {
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
            return;
        }
        // Fetch suggestions from backend
        const resp = await fetch(`/tags?q=${encodeURIComponent(q)}`);
        const tags = await resp.json();
        // Only show suggestions not already added
        const filtered = tags.filter(tag => !currentTags.some(t => t.id == tag.id));
        tagSuggestions.innerHTML = '';
        if (filtered.length === 0) {
            tagSuggestions.style.display = 'none';
            return;
        }
        filtered.forEach((tag, idx) => {
            const item = document.createElement('div');
            item.className = 'tag-suggestion-item';
            item.textContent = tag.name;
            item.dataset.tagId = tag.id;
            if (idx === 0) item.classList.add('active'); // highlight first by default
            item.addEventListener('mousedown', (e) => {
                // mousedown instead of click to beat blur event
                e.preventDefault();
                addTagPill(tag);
            });
            tagSuggestions.appendChild(item);
        });
        tagSuggestions.style.display = 'block';
    });

    // Add tag on enter or tab, arrow navigation
    tagInput.addEventListener('keydown', async function (e) {
        const items = tagSuggestions.querySelectorAll('.tag-suggestion-item');
        let activeIdx = Array.from(items).findIndex(item => item.classList.contains('active'));
        if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            let tag;
            const items = tagSuggestions.querySelectorAll('.tag-suggestion-item');
            let activeIdx = Array.from(items).findIndex(item => item.classList.contains('active'));
            if (tagSuggestions.style.display === 'block' && activeIdx >= 0 && items[activeIdx]) {
                // Choose from suggestion
                tag = { id: items[activeIdx].dataset.tagId, name: items[activeIdx].textContent };
            } else if (tagInput.value.trim()) {
                // Create new tag if not exist
                const newTagName = tagInput.value.trim();
                const resp = await fetch('/newtag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.csrf_token },
                    body: JSON.stringify({ name: newTagName })
                });
                if (resp.ok) {
                    tag = await resp.json();
                }
            }
            if (tag) addTagPill(tag);
            tagInput.value = '';
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
        }

        else if (e.key === "ArrowDown" && items.length > 0) {
            e.preventDefault();
            let newIdx = (activeIdx + 1) % items.length;
            items.forEach(item => item.classList.remove('active'));
            items[newIdx].classList.add('active');
            tagInput.value = items[newIdx].textContent;
        } else if (e.key === "ArrowUp" && items.length > 0) {
            e.preventDefault();
            let newIdx = (activeIdx - 1 + items.length) % items.length;
            items.forEach(item => item.classList.remove('active'));
            items[newIdx].classList.add('active');
            tagInput.value = items[newIdx].textContent;
        } else if (e.key === "Escape") {
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
        }
    });

    // Hide suggestions when input loses focus (but allow click to register)
    tagInput.addEventListener('blur', function () {
        setTimeout(() => {
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
        }, 120);
    });

    // Hide suggestions if clicking anywhere outside input or dropdown
    document.addEventListener('mousedown', function (e) {
        if (!tagInput.contains(e.target) && !tagSuggestions.contains(e.target)) {
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
        }
    });

    function addTagPill(tag) {
        if (currentTags.some(t => t.id == tag.id)) return;
        const pill = document.createElement('span');
        pill.className = 'tag-pill';
        pill.dataset.tagId = tag.id;
        pill.innerHTML = `
            ${tag.name}
            <span class="remove-tag" title="Remove tag">&times;</span>
        `;
        tagBar.insertBefore(pill, tagInput);
        currentTags.push(tag);
        renderTagIds();
        tagInput.value = '';
        tagSuggestions.style.display = 'none';
        tagSuggestions.innerHTML = '';
    }

    renderTagIds();
});
