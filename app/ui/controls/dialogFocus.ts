// What every dialog does with the keyboard: it takes the focus when it opens (so Escape and Tab work
// at once), keeps Tab inside itself, and gives the focus back to where it was when it closes.

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function dialogFocus(node: HTMLElement): { destroy: () => void } {
  const before =
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
  // Asked a moment later, so a field the dialog focuses itself while opening is not overridden.
  queueMicrotask(() => {
    if (!node.contains(document.activeElement)) node.focus();
  });

  function onKey(event: KeyboardEvent): void {
    if (event.key !== "Tab") return;
    const stops = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (el) => el.offsetParent !== null,
    );
    const first = stops[0];
    const last = stops[stops.length - 1];
    if (!first || !last) return;
    const at = document.activeElement;
    if (event.shiftKey && (at === first || at === node)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && at === last) {
      event.preventDefault();
      first.focus();
    }
  }
  node.addEventListener("keydown", onKey);

  return {
    destroy() {
      node.removeEventListener("keydown", onKey);
      if (before?.isConnected) before.focus();
    },
  };
}
