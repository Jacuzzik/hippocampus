// Hippocampus home page scroll effects: a memory trail, headings that decode, pictures that drift.
// Decoration only: the page reads the same without this script, and reduced motion skips all of it.

const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!RM) init();
markSwing();

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

// The brand mark swings toward the scroll, eased, so it trails the page instead of snapping to it.
function markSwing() {
  const wide = matchMedia("(min-width: 1100px)").matches;
  if (!wide) return;
  const mark = document.createElement("div");
  mark.className = "scroll-mark";
  mark.setAttribute("aria-hidden", "true");
  const img = document.createElement("img");
  img.src = "img/hippocampus-mark-purple.png";
  img.alt = "";
  img.width = 440;
  img.height = 440;
  mark.append(img);
  document.body.append(mark);

  let cur = scrollY;
  let raf = 0;
  let last = 0;
  const step = (time) => {
    raf = 0;
    const dt = last ? Math.min(time - last, 64) : 16;
    last = time;
    cur += (scrollY - cur) * (1 - Math.exp(-dt / 180));
    const moving = Math.abs(scrollY - cur) > 0.1;
    mark.style.transform = `translate3d(0, ${(cur * 0.12).toFixed(1)}px, 0) rotate(${(Math.sin(cur / 600) * 9).toFixed(2)}deg)`;
    if (moving) raf = requestAnimationFrame(step);
    else last = 0;
  };
  const queue = () => {
    if (!raf) raf = requestAnimationFrame(step);
  };
  addEventListener("scroll", queue, { passive: true });
  queue();
}
