(() => {
    const toggle = document.querySelector("[data-password-toggle]");
    const password = document.getElementById("id_password");
    if (!toggle || !password) return;

    toggle.addEventListener("click", () => {
        const reveal = password.type === "password";
        password.type = reveal ? "text" : "password";
        toggle.setAttribute("aria-pressed", String(reveal));
        toggle.setAttribute(
            "aria-label",
            reveal ? toggle.dataset.hideLabel : toggle.dataset.showLabel
        );
    });
})();
