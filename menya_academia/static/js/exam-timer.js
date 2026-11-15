(() => {
    const timer = document.querySelector(".timer-card[data-deadline]");
    const form = document.getElementById("exam-form");
    const finishFlag = document.getElementById("finish-flag");
    const display = document.getElementById("exam-timer");
    if (!timer || !form || !finishFlag || !display) return;

    const deadline = Date.parse(timer.dataset.deadline);
    if (!Number.isFinite(deadline)) return;
    let submitted = false;

    const update = () => {
        if (submitted) return;
        const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        display.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
        if (remaining === 0) {
            submitted = true;
            finishFlag.value = "1";
            form.requestSubmit();
        }
    };

    update();
    window.setInterval(update, 1000);
})();
