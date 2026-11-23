(() => {
    const layer = document.querySelector(".confetti-layer");
    if (!layer || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const colors = ["#1663d6", "#17a78b", "#f1b643", "#ef6f6c", "#8b77d8", "#2ec7a3", "#ff8fb1"];
    const flowers = ["✿", "❀", "✾", "❁", "✦"];
    const total = 90;

    for (let index = 0; index < total; index += 1) {
        const piece = document.createElement("span");
        const isFlower = index % 5 === 0;
        piece.className = isFlower ? "confetti-piece confetti-flower" : "confetti-piece";
        piece.style.left = `${Math.random() * 100}%`;
        piece.style.animationDelay = `${Math.random() * 1.8}s`;
        piece.style.animationDuration = `${3 + Math.random() * 2.4}s`;
        piece.style.setProperty("--drift", `${(Math.random() - 0.5) * 120}px`);
        if (isFlower) {
            piece.textContent = flowers[index % flowers.length];
            piece.style.fontSize = `${16 + Math.random() * 14}px`;
        } else {
            piece.style.backgroundColor = colors[index % colors.length];
            piece.style.width = `${6 + Math.random() * 8}px`;
            piece.style.height = `${10 + Math.random() * 12}px`;
            piece.style.borderRadius = Math.random() > 0.5 ? "999px" : "2px";
        }
        layer.appendChild(piece);
    }

    window.setTimeout(() => layer.remove(), 6500);
})();