// Update Manager client scripts

document.addEventListener("DOMContentLoaded", () => {
    // Copy to clipboard handler
    document.querySelectorAll(".copy-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const textToCopy = btn.getAttribute("data-clipboard");
            if (!textToCopy) return;

            try {
                await navigator.clipboard.writeText(textToCopy);
                const originalText = btn.textContent;
                btn.textContent = "Copied! ✓";
                btn.style.backgroundColor = "#16a34a";
                btn.style.color = "#ffffff";

                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.backgroundColor = "";
                    btn.style.color = "";
                }, 2000);
            } catch (err) {
                console.error("Failed to copy:", err);
            }
        });
    });

    // Auto-dismiss alert banners after 8 seconds
    const alerts = document.querySelectorAll(".alert-banner");
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.5s ease-out";
            alert.style.opacity = "0";
            setTimeout(() => {
                alert.style.display = "none";
            }, 500);
        }, 8000);
    });
});
