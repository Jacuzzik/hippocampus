<script lang="ts">
  import { ORB_LABELS, type OrbState } from "./model";

  let { state = "idle" }: { state?: OrbState } = $props();
</script>

<span
  class="orb"
  data-state={state}
  role="status"
  aria-label="Assistant: {ORB_LABELS[state]}"
>
  <span class="core" aria-hidden="true"></span>
</span>

<style>
  .orb {
    --orb-color: var(--color-text-subtle);
    display: inline-grid;
    place-items: center;
    width: var(--space-5);
    height: var(--space-5);
    border-radius: 50%;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    transition:
      border-color 200ms ease,
      background-color 200ms ease;
  }

  .core {
    width: 60%;
    height: 60%;
    border-radius: 50%;
    background: var(--orb-color);
    transition:
      background-color 200ms ease,
      transform 200ms ease;
  }

  .orb[data-state="listening"] {
    --orb-color: var(--color-confirm);
    border-color: var(--color-confirm);
  }

  .orb[data-state="thinking"] {
    --orb-color: var(--color-think);
    border-color: var(--color-think);
  }

  .orb[data-state="speaking"] {
    --orb-color: var(--color-text);
    border-color: var(--color-text);
  }

  /* Reduced motion: the state still shows in colour and the label, just without the pulse. */
  @media (prefers-reduced-motion: no-preference) {
    .orb[data-state="thinking"] {
      animation: pulse 1.2s ease-in-out infinite;
    }

    .orb[data-state="speaking"] {
      animation: pulse 0.6s ease-in-out infinite;
    }
  }

  @keyframes pulse {
    50% {
      transform: scale(1.25);
    }
  }
</style>
