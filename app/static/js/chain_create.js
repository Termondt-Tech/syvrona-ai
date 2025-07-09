// chain_create.js

document.addEventListener("DOMContentLoaded", function () {
    // Live search filter
    const promptSearch = document.getElementById("prompt-search");
    const promptList = document.getElementById("prompt-list");
    const stepList = document.getElementById("chain-steps-list");

    // --- 1. Live Search ---
    promptSearch.addEventListener("input", function () {
        const query = promptSearch.value.toLowerCase().trim();
        Array.from(promptList.children).forEach((item) => {
            const title = item.querySelector(".prompt-title").textContent.toLowerCase();
            const desc = item.querySelector(".prompt-desc").textContent.toLowerCase();
            if (title.includes(query) || desc.includes(query)) {
                item.style.display = "";
            } else {
                item.style.display = "none";
            }
        });
    });

    // --- 2. Add Step ---
    promptList.addEventListener("click", function (e) {
        if (e.target.classList.contains("add-step-btn")) {
            const li = e.target.closest("li");
            const promptId = li.getAttribute("data-prompt-id");
            const title = li.querySelector(".prompt-title").textContent;

            // Create new step item
            const stepItem = document.createElement("li");
            stepItem.className = "chain-step-item";
            stepItem.setAttribute("data-prompt-id", promptId);

            stepItem.innerHTML = `
                <span class="prompt-title">${title}</span>
                <button type="button" class="btn btn-sm btn-order-up" title="Move Up">&#8593;</button>
                <button type="button" class="btn btn-sm btn-order-down" title="Move Down">&#8595;</button>
                <button type="button" class="btn btn-danger btn-sm remove-step-btn" title="Remove">&times;</button>
                <input type="hidden" name="prompt_ids[]" value="${promptId}">
            `;
            stepList.appendChild(stepItem);

            // Disable the add button for this prompt
            e.target.disabled = true;
            li.classList.add("added-to-chain");
        }
    });

    // --- 3. Step Ordering and Remove ---
    stepList.addEventListener("click", function (e) {
        const item = e.target.closest("li");
        if (!item) return;

        // Move Up
        if (e.target.classList.contains("btn-order-up")) {
            if (item.previousElementSibling) {
                stepList.insertBefore(item, item.previousElementSibling);
            }
        }
        // Move Down
        else if (e.target.classList.contains("btn-order-down")) {
            if (item.nextElementSibling) {
                stepList.insertBefore(item.nextElementSibling, item);
            }
        }
        // Remove
        else if (e.target.classList.contains("remove-step-btn")) {
            const promptId = item.getAttribute("data-prompt-id");
            // Enable the Add button back in prompt list
            const promptLi = promptList.querySelector(`li[data-prompt-id="${promptId}"]`);
            if (promptLi) {
                const addBtn = promptLi.querySelector(".add-step-btn");
                addBtn.disabled = false;
                promptLi.classList.remove("added-to-chain");
            }
            item.remove();
        }
    });

    // Optional: On submit, update hidden input order (in case of drag/drop/manual manipulation)
    document.getElementById("create-chain-form").addEventListener("submit", function () {
        // Remove all existing prompt_ids hidden fields
        Array.from(stepList.querySelectorAll('input[name="prompt_ids[]"]')).forEach(el => el.remove());

        // Add new hidden fields in current order
        Array.from(stepList.children).forEach((li) => {
            const promptId = li.getAttribute("data-prompt-id");
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "prompt_ids[]";
            input.value = promptId;
            li.appendChild(input);
        });
    });
});
