const dialog = document.querySelector("#screenshot-dialog");
let opener;
if (dialog instanceof HTMLDialogElement) {
  const image = dialog.querySelector("img");
  const title = dialog.querySelector("h2");
  const original = dialog.querySelector("[data-original]");
  document.querySelectorAll("[data-screenshot]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
        return;
      event.preventDefault();
      opener = link;
      image.src = link.href;
      image.alt = link.dataset.caption;
      title.textContent = link.dataset.caption;
      original.href = link.href;
      dialog.showModal();
    });
  });
  dialog
    .querySelector("button")
    .addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => opener?.focus());
}
const links = Array.from(document.querySelectorAll(".case-tree a"));
function selectCase(id) {
  links.forEach((link) => {
    if (link.hash === `#${id}`) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}
links.forEach((link) =>
  link.addEventListener("click", () => selectCase(link.hash.slice(1))),
);
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      const entry = entries.find((item) => item.isIntersecting);
      if (entry) selectCase(entry.target.id);
    },
    { rootMargin: "-10% 0px -65% 0px" },
  );
  document
    .querySelectorAll("article.case")
    .forEach((article) => observer.observe(article));
}
