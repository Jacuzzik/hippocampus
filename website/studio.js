// Hippocampus website: reading progress, the top bar, chapter index, the walk-through strip and the
// "on this page" list. Everything here is decoration: each page reads the same without it.

const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const WIDE = matchMedia("(min-width: 901px)");
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const top = document.querySelector("[data-top]");
const bar = document.querySelector("[data-progress]");
const pin = document.querySelector(".pin");
const track = document.querySelector("[data-track]");

let ticking = false;
function frame() {
  ticking = false;
  const max = document.documentElement.scrollHeight - innerHeight;
  const read = max > 0 ? clamp(scrollY / max, 0, 1) : 0;
  if (bar) bar.parentElement.parentElement.style.setProperty("--read", read.toFixed(4));
  if (top) top.classList.toggle("scrolled", scrollY > 8);

  if (pin && track && WIDE.matches && !RM) {
    const r = pin.getBoundingClientRect();
    const span = pin.offsetHeight - innerHeight;
    const p = span > 0 ? clamp(-r.top / span, 0, 1) : 0;
    const viewport = track.parentElement;
    const travel = Math.max(0, track.scrollWidth - viewport.clientWidth);
    track.style.setProperty("--x", `${(-p * travel).toFixed(1)}px`);
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

// Chapter index: the link for the chapter in view is marked.
const links = new Map(
  [...document.querySelectorAll(".chapters a[href^='#']")].map((a) => [a.getAttribute("href").slice(1), a]),
);
if (links.size && "IntersectionObserver" in window) {
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        for (const a of links.values()) a.removeAttribute("aria-current");
        const a = links.get(e.target.id);
        if (a) a.setAttribute("aria-current", "true");
      }
    },
    { rootMargin: "-40% 0px -55% 0px" },
  );
  for (const id of links.keys()) {
    const el = document.getElementById(id);
    if (el) io.observe(el);
  }
}

// Content pages: build the "on this page" list from the headings.
const toc = document.querySelector("[data-toc]");
if (toc) {
  const heads = [...document.querySelectorAll(".doc h2")];
  if (heads.length < 2) {
    toc.closest("[data-toc-wrap]")?.setAttribute("hidden", "");
  } else {
    for (const h of heads) {
      if (!h.id) h.id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${h.id}`;
      a.textContent = h.textContent.replace(/^\d+\.\s*/, "");
      li.append(a);
      toc.append(li);
    }
    const tocLinks = [...toc.querySelectorAll("a")];
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          tocLinks.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === `#${e.target.id}`));
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    heads.forEach((h) => io.observe(h));
  }
}
