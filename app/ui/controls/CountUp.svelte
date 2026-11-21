<!-- 12.08: a number that counts up (or down) to its new value, so a change reads as movement.
     Shows the target at once when motion is off. The text always ends on the exact value. -->
<script lang="ts">
  import { still } from "../motion.ts";

  type Props = {
    value: number | null | undefined;
    suffix?: string;
    none?: string;
  };
  let { value, suffix = "%", none = "–" }: Props = $props();

  const DURATION_MS = 600;
  let shown = $state<number | null>(null);
  let frame = 0;

  $effect(() => {
    const target = value ?? null;
    cancelAnimationFrame(frame);
    const from = shown;
    if (target === null || from === null || from === target || still()) {
      shown = target;
      return;
    }
    const start = performance.now();
    const step = (now: number): void => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - (1 - t) ** 3;
      shown = Math.round(from + (target - from) * eased);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  });
</script>

{shown === null ? none : `${shown}${suffix}`}
