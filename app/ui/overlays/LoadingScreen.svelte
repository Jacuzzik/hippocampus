<script lang="ts">
  // Shown over the app on startup: no solid colour. The app behind is blurred, with the white logo and name on top.
  // When the vault and the agent terminals have loaded (the `ready` prop), the logo holds for a moment,
  // then the blur and the logo fade out together, revealing the dashboard.
  // A 2-minute safety cap lifts it even if something hangs.
  import logo from "../assets/brand/hippocampus-mark-mask.png";
  import { prefs } from "../prefs.svelte.ts";

  let { ready }: { ready: boolean } = $props();

  // Time the logo stays after loading finishes, then how long the blur and the logo take to fade.
  // Settings > Appearance > Start-up logo picks the long or the short pair, or "off" for neither.
  const TIMES = { long: [10000, 2500], short: [1000, 600] } as const;
  // Read once at start: changing the setting applies from the next launch.
  const intro = prefs.intro;
  const [HOLD_MS, FADE_MS] = TIMES[intro === "off" ? "short" : intro];

  let phase = $state<"loading" | "fading" | "gone">("loading");
  let timedOut = $state(false);

  $effect(() => {
    // Safety cap only: lift after 2 minutes even if a terminal hangs.
    const limit = setTimeout(() => (timedOut = true), 120000);
    return () => clearTimeout(limit);
  });

  $effect(() => {
    if (phase !== "loading" || !(ready || timedOut)) return;
    // Reduced motion, or the logo turned off: skip the hold and the fade and lift the screen at once.
    if (intro === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      phase = "gone";
      return;
    }
    const hold = setTimeout(() => (phase = "fading"), HOLD_MS);
    return () => clearTimeout(hold);
  });

  $effect(() => {
    if (phase !== "fading") return;
    // Once the blur and the logo have faded, the overlay is removed.
    const done = setTimeout(() => (phase = "gone"), FADE_MS);
    return () => clearTimeout(done);
  });
</script>

{#if phase !== "gone"}
  <div
    class="loading"
    class:fading={phase === "fading"}
    style="--fade-ms: {FADE_MS}ms"
    role="status"
    aria-live="polite"
  >
    <div class="lockup" class:fading={phase === "fading"}>
      <div class="logo" style="--mark: url({logo})" aria-hidden="true"></div>
      <span class="name">Hippocampus</span>
    </div>
  </div>
{/if}

<style>
  .loading {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    place-items: center;
    padding: max(16px, env(safe-area-inset-top, 0px)) max(16px, env(safe-area-inset-right, 0px))
      max(16px, env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px));
  }
  /* The blurred view of the app behind, with a light dark tint so the white logo reads.
     It fades with the same timing and easing as the logo, so the two always reach zero together. */
  .loading::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--color-scrim-soft);
    -webkit-backdrop-filter: blur(48px);
    backdrop-filter: blur(48px);
    opacity: 1;
    transition: opacity var(--fade-ms) ease;
  }
  .loading.fading::before {
    opacity: 0;
  }
  /* The mark with the name written on its right. */
  .lockup {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 100%;
    transition: opacity var(--fade-ms) ease;
  }
  .lockup.fading {
    opacity: 0;
  }
  .name {
    /* The app's UI font, the same token the rest of the app uses. */
    font-family: var(--font-ui);
    font-size: 48px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--color-on-strong);
    white-space: nowrap;
  }
  /* The mark is a mask, so it takes white and sits with no box of its own. */
  .logo {
    width: 90px;
    height: 90px;
    flex: none;
    max-width: 100%;
    background: var(--color-on-strong);
    -webkit-mask: var(--mark) center / contain no-repeat;
    mask: var(--mark) center / contain no-repeat;
  }
</style>
