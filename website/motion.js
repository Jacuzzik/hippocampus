// Hippocampus website motion. Everything here is decoration: the page reads the same without it.
// One scroll loop sets a few CSS variables; motion.css turns them into perspective, tilt and drift.
// Visitors who ask for reduced motion get the still page.

const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const FINE = matchMedia("(hover: hover) and (pointer: fine)").matches;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

document.documentElement.classList.add("motion");
if (RM) document.documentElement.classList.add("still");

/* ---- Reveal: sections rise and straighten as they come into view -------------------------------- */
const autoReveal = ".section .intro, .group-head, .plan, .cards li, .os > *, .faq details, .closing > *";
document.querySelectorAll(autoReveal).forEach((el) => el.setAttribute("data-reveal", ""));
// Siblings that arrive together get a small stagger.
document.querySelectorAll("[data-reveal]").forEach((el) => {
  const peers = [...el.parentElement.children].filter((c) => c.hasAttribute("data-reveal"));
  el.style.setProperty("--d", String(peers.indexOf(el)));
});
if (RM || !("IntersectionObserver" in window)) {
  document.querySelectorAll("[data-reveal]").forEach((el) => el.classList.add("in"));
} else {
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
    },
    { rootMargin: "0px 0px -10% 0px" },
  );
  document.querySelectorAll("[data-reveal]").forEach((el) => io.observe(el));
}

/* ---- Tilt: cards lean toward the pointer, with a light sheen that follows it --------------------- */
if (FINE && !RM) {
  for (const el of document.querySelectorAll("[data-tilt]")) {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      el.style.setProperty("--ry", ((x - 0.5) * 8).toFixed(2) + "deg");
      el.style.setProperty("--rx", ((0.5 - y) * 6).toFixed(2) + "deg");
      el.style.setProperty("--gx", (x * 100).toFixed(1) + "%");
      el.style.setProperty("--gy", (y * 100).toFixed(1) + "%");
      el.classList.add("lean");
    });
    el.addEventListener("pointerleave", () => {
      el.classList.remove("lean");
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
    });
  }
}

/* ---- Team deck: each card knows how far it sits behind the front one ---------------------------- */
const deck = document.getElementById("role-card");
if (deck) {
  const cards = [...deck.querySelectorAll("[data-card]")];
  const place = () => {
    const front = Math.max(0, cards.findIndex((c) => c.dataset.card === deck.dataset.active));
    cards.forEach((c, i) => {
      const k = (i - front + cards.length) % cards.length;
      c.style.setProperty("--k", String(k));
      c.classList.toggle("front", k === 0);
      c.classList.toggle("hidden", k > 3);
    });
  };
  place();
  new MutationObserver(place).observe(deck, { attributes: true, attributeFilter: ["data-active"] });
}

/* ---- Hero: the app window and its two sheets settle from a tilted stack as you scroll ------------ */
const hero = document.querySelector("[data-hero]");
const drifters = [...document.querySelectorAll("[data-drift]")];
let mx = 0;
let my = 0;
if (hero && FINE && !RM)
  document.querySelector(".hero")?.addEventListener("pointermove", (e) => {
    mx = e.clientX / innerWidth - 0.5;
    my = e.clientY / innerHeight - 0.5;
    queue();
  });

let ticking = false;
function frame() {
  ticking = false;
  if (!hero || RM) return;
  const r = hero.getBoundingClientRect();
  const p = clamp(1 - (r.top - innerHeight * 0.2) / (innerHeight * 0.7), 0, 1);
  hero.style.setProperty("--p", p.toFixed(3));
  hero.style.setProperty("--mx", mx.toFixed(3));
  hero.style.setProperty("--my", my.toFixed(3));
  for (const d of drifters) {
    const k = Number(d.dataset.drift);
    d.style.setProperty("--dy", (r.top * k).toFixed(1) + "px");
    d.style.setProperty("--dx", (mx * k * 160).toFixed(1) + "px");
  }
}
function queue() {
  if (!ticking) {
    ticking = true;
    requestAnimationFrame(frame);
  }
}
addEventListener("scroll", queue, { passive: true });
addEventListener("resize", queue);
frame();
