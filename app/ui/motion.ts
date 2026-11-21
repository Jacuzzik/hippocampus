/** True when motion is off: the Motion setting, quiet mode, or the computer's reduced-motion choice. */
export function still(): boolean {
  const motion = document.documentElement.dataset.motion;
  return (
    motion === "off" ||
    (motion !== "on" &&
      typeof matchMedia === "function" &&
      matchMedia("(prefers-reduced-motion: reduce)").matches)
  );
}
