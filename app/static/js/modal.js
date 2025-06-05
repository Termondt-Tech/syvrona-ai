
function showConfirmModal(title, message, options = {}) {
    // options: {mode: "alert"|"confirm"}
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-message').textContent = message;

        // Buttons
        const okBtn = document.getElementById('modal-ok');
        const confirmBtn = document.getElementById('modal-confirm');
        const cancelBtn = document.getElementById('modal-cancel');

        // Hide/show buttons based on mode
        if (options.mode === "alert") {
            okBtn.style.display = '';
            confirmBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
        } else {
            okBtn.style.display = 'none';
            confirmBtn.style.display = '';
            cancelBtn.style.display = '';
        }

        modal.style.display = 'flex';

        // Cleanup function
        function cleanup(result) {
            modal.style.display = 'none';
            okBtn.removeEventListener('click', okHandler);
            confirmBtn.removeEventListener('click', confirmHandler);
            cancelBtn.removeEventListener('click', cancelHandler);
            resolve(result);
        }

        // Handlers
        function okHandler() { cleanup(true); }
        function confirmHandler() { cleanup(true); }
        function cancelHandler() { cleanup(false); }

        // Attach/detach handlers as needed
        okBtn.addEventListener('click', okHandler);
        confirmBtn.addEventListener('click', confirmHandler);
        cancelBtn.addEventListener('click', cancelHandler);
    });
}


document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.action-confirm-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const title = form.dataset.confirmTitle || 'Confirm Action';
            const message = form.dataset.confirmMessage || 'Are you sure?';
            showConfirmModal(title, message).then(confirmed => {
                if (confirmed) form.submit();
            });
        });
    });
});
