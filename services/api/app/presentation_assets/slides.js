document.getElementById("print").addEventListener("click", () => window.print());
document.addEventListener("keydown", (event) => {
  if (!["ArrowRight", "ArrowLeft", "PageDown", "PageUp"].includes(event.key)) return;
  const slides = [...document.querySelectorAll(".slide")];
  const current = slides.reduce((best, slide, index) =>
    Math.abs(slide.getBoundingClientRect().top - 60) < Math.abs(slides[best].getBoundingClientRect().top - 60) ? index : best, 0);
  const step = ["ArrowRight", "PageDown"].includes(event.key) ? 1 : -1;
  slides[Math.max(0, Math.min(slides.length - 1, current + step))].scrollIntoView();
  event.preventDefault();
});
