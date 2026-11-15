(() => {
    const form = document.getElementById("exam-form");
    const status = document.getElementById("answer-save-status");
    const translations = document.getElementById("answer-save-translations");
    if (!form || !status || !translations) return;

    let pendingOption = null;
    let saving = false;

    const save = async (option) => {
        status.textContent = translations.dataset.savingText;
        const data = new FormData();
        data.set("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);
        data.set("question_id", form.querySelector("[name=question_id]").value);
        data.set("option", option.value);
        try {
            const response = await fetch(form.dataset.saveUrl, {
                method: "POST",
                body: data,
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || translations.dataset.saveFailedText);
            }
            status.textContent = status.dataset.savedText;
        } catch (error) {
            status.textContent = error instanceof TypeError
                ? translations.dataset.connectionErrorText
                : error.message || translations.dataset.saveFailedText;
        }
    };

    const saveLatestSelection = async () => {
        if (saving) return;
        saving = true;
        while (pendingOption) {
            const option = pendingOption;
            pendingOption = null;
            await save(option);
        }
        saving = false;
    };

    form.querySelectorAll('input[name="option"]').forEach((option) => {
        option.addEventListener("change", () => {
            pendingOption = option;
            saveLatestSelection();
        });
    });
})();
