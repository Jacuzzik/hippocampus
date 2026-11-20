// Hippocampus home page scroll effects: a memory trail, headings that decode, pictures that drift.
// Decoration only: the page reads the same without this script, and reduced motion skips all of it.

const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!RM) init();

function init() {
  const sections = [...document.querySelectorAll("section[id], section.closing")];
  const rail = document.createElement("nav");
  rail.className = "trail";
  rail.setAttribute("aria-hidden", "true");
  const fill = document.createElement("i");
  fill.className = "fill";
  rail.append(fill);
  const dots = sections.map((s, i) => {
    const d = document.createElement("b");
    d.className = "dot";
    d.style.top = `${(i / Math.max(1, sections.length - 1)) * 100}%`;
    rail.append(d);
    return d;
  });
  document.body.append(rail);

  const drifters = [...document.querySelectorAll(".tile .shot img")];
  let ticking = false;

  const frame = () => {
    ticking = false;
    const h = innerHeight;
    const docH = document.documentElement.scrollHeight - h;
    const prog = docH > 0 ? Math.min(1, Math.max(0, scrollY / docH)) : 0;
    fill.style.setProperty("--prog", prog.toFixed(4));

    sections.forEach((s, i) => {
      const r = s.getBoundingClientRect();
      const on = r.top < h * 0.5 && r.bottom > h * 0.5;
      const past = r.top < h * 0.5;
      dots[i].classList.toggle("lit", past || on);
    });

    for (const img of drifters) {
      const r = img.getBoundingClientRect();
      if (r.bottom < 0 || r.top > h) continue;
      const mid = r.top + r.height / 2;
      const sy = Math.max(-14, Math.min(14, (h / 2 - mid) * 0.06));
      img.style.setProperty("--sy", `${sy.toFixed(1)}px`);
    }
  };
  const queue = () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(frame);
    }
  };
  addEventListener("scroll", queue, { passive: true });
  addEventListener("resize", queue);
  frame();

  // Headings decode from mono glyphs into their words the first time they come into view.
  const GLYPHS = "01<>[]/_#*+=";
  const decode = (el) => {
    const text = el.textContent;
    const steps = 16;
    let t = 0;
    const id = setInterval(() => {
      t += 1;
      const keep = Math.floor((text.length * t) / steps);
      const rest = [...text.slice(keep)]
        .map((c) => (c === " " ? " " : GLYPHS[(Math.random() * GLYPHS.length) | 0]))
        .join("");
      el.textContent = text.slice(0, keep) + rest;
      if (t >= steps) {
        clearInterval(id);
        el.textContent = text;
      }
    }, 38);
  };
  const heads = [...document.querySelectorAll("section h2")].filter((h) => h.children.length === 0);
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries)
          if (e.isIntersecting) {
            decode(e.target);
            io.unobserve(e.target);
          }
      },
      { rootMargin: "0px 0px -15% 0px" },
    );
    heads.forEach((h) => io.observe(h));
  }
}
