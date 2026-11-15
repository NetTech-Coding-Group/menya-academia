(() => {
    const layer = document.querySelector(".confetti-layer");
    if (!layer || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const colors = ["#1663d6", "#17a78b", "#f1b643", "#ef6f6c", "#8b77d8"];
    for (let index = 0; index < 70; index += 1) {
        const piece = document.createElement("span");
        piece.className = "confetti-piece";
        piece.style.left = `${Math.random() * 100}%`;
        piece.style.backgroundColor = colors[index % colors.length];
        piece.style.animationDelay = `${Math.random() * 1.4}s`;
        piece.style.animationDuration = `${2.4 + Math.random() * 1.8}s`;
        layer.appendChild(piece);
    }
    window.setTimeout(() => layer.remove(), 5200);
})();
