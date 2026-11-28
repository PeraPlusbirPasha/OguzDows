/* Optional enhancement only. All content, navigation and downloads work without JS. */
"use strict";

for (const button of document.querySelectorAll("[data-copy]")) {
  button.addEventListener("click", async () => {
    const value = button.dataset.copy;
    const label = button.dataset.label || "Metin";
    let status = button.parentElement.querySelector(".copy-status");
    if (!status) {
      status = document.createElement("span");
      status.className = "copy-status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      button.after(status);
    }
    try {
      if (!navigator.clipboard || !window.isSecureContext) {
        throw new Error("Clipboard unavailable");
      }
      await navigator.clipboard.writeText(value);
      status.textContent = `${label} kopyalandı.`;
    } catch {
      // Never send to a server or request another permission to copy a public hash.
      status.textContent = `${label}: ${value} — seçip elle kopyalayabilirsin.`;
    }
  });
}

const mobileMenu = document.querySelector(".mobile-menu");
mobileMenu?.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && mobileMenu.open) {
    mobileMenu.open = false;
    mobileMenu.querySelector("summary").focus();
  }
});
