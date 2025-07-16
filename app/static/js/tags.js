// static/js/tags.js
document.addEventListener('DOMContentLoaded', () => {
    // Open rename modal
    document.querySelectorAll('.btn-rename').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('renameTagId').value = btn.dataset.tagId;
            document.getElementById('newTagName').value = btn.dataset.tagName;
            openModal('renameTagModal');
        });
    });

    // Handle rename submit
    document.getElementById('renameTagForm').addEventListener('submit', async (e) => {
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
            // Update UI
            document.querySelector(`.btn-rename[data-tag-id="${tagId}"]`).closest('.tag-pill').childNodes[0].textContent = newName + " ";
            closeModal('renameTagModal');
        } else {
            msg.textContent = data.error || "Rename failed";
        }
    });

    // Open delete modal
    document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('deleteTagId').value = btn.dataset.tagId;
            document.getElementById('deleteTagConfirm').textContent = `Are you sure you want to delete tag "${btn.dataset.tagName}"? This cannot be undone.`;
            openModal('deleteTagModal');
        });
    });

    // Handle delete submit
    document.getElementById('deleteTagForm').addEventListener('submit', async (e) => {
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

    // Modal open/close utils
    function openModal(id) {
        const m = document.getElementById(id);
        m.style.display = 'block';
        m.setAttribute('aria-hidden', 'false');
        m.querySelector('input, button').focus();
    }
    function closeModal(id) {
        const m = document.getElementById(id);
        m.style.display = 'none';
        m.setAttribute('aria-hidden', 'true');
    }
    document.querySelectorAll('.close-modal').forEach(btn => btn.addEventListener('click', e => {
        closeModal(btn.closest('.modal').id);
    }));
    // Optional: ESC closes modals
    document.addEventListener('keydown', e => {
        if (e.key === "Escape") Array.from(document.querySelectorAll('.modal')).forEach(m => closeModal(m.id));
    });
});