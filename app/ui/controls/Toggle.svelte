<script lang="ts">
  // The one on/off switch: a 36x18 track with a knob, accent when on. It is a real checkbox underneath, so
  // keyboard, screen readers and `getByRole("checkbox")` all work. The input sits over the track, so a click
  // anywhere on the switch or its words flips it.
  let {
    checked = $bindable(false),
    label = "",
    ariaLabel,
    disabled = false,
    onchange,
  }: {
    checked?: boolean;
    label?: string;
    ariaLabel?: string;
    disabled?: boolean;
    onchange?: (value: boolean) => void;
  } = $props();
</script>

<label class="toggle" class:disabled>
  <span class="box">
    <input
      type="checkbox"
      bind:checked
      {disabled}
      aria-label={ariaLabel}
      onchange={(e) => onchange?.(e.currentTarget.checked)}
    />
    <span class="track"></span>
  </span>
  {#if label}<span>{label}</span>{/if}
</label>

<style>
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
    font-size: var(--font-size-xs);
  }

  .toggle.disabled {
    cursor: default;
    color: var(--color-text-subtle);
  }

  .box {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 18px;
    flex: none;
  }

  input {
    position: absolute;
    inset: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    cursor: inherit;
  }

  .track {
    position: absolute;
    inset: 0;
    border-radius: var(--radius-sm);
    background: var(--color-border);
    transition: background var(--duration-fast) var(--ease-standard);
  }

  .track::after {
    content: "";
    position: absolute;
    top: 3px;
    left: 3px;
    width: 12px;
    height: 12px;
    border-radius: var(--radius-sm);
    background: var(--color-bg-0);
    transition: transform var(--duration-fast) var(--ease-standard);
  }

  input:checked + .track {
    background: var(--color-accent);
  }

  input:checked + .track::after {
    transform: translateX(18px);
  }

  input:focus-visible + .track {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  input:disabled + .track {
    opacity: 0.5;
  }

  /* Touch screens: the label is the touch target, so it takes the minimum height. */
  @media (max-width: 1100px), (pointer: coarse) {
    .toggle {
      min-height: var(--layout-touch-target);
    }
  }
</style>
