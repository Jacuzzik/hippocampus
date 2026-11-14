<!-- The app's own dropdown: a solid, square button that opens a solid list. Replaces the native select. -->
<script lang="ts">
  type Option = { value: string; label: string };

  let {
    options,
    value = $bindable(""),
    disabled = false,
    label,
    onchange,
  }: {
    options: Option[];
    value?: string;
    disabled?: boolean;
    label: string;
    onchange?: (value: string) => void;
  } = $props();

  let open = $state(false);
  let root: HTMLDivElement | undefined = $state();
  let menu: HTMLUListElement | undefined = $state();
  // A list that opens at the bottom of a scrolling page is brought into view, so no choice is cut off.
  $effect(() => {
    if (open) menu?.scrollIntoView({ block: "nearest" });
  });
  const shown = $derived(
    options.find((o) => o.value === value)?.label ?? (value || "Choose"),
  );

  function pick(next: string): void {
    value = next;
    open = false;
    onchange?.(next);
  }

  // A click outside the dropdown closes its list.
  function onWindowClick(event: MouseEvent): void {
    if (open && root && !root.contains(event.target as Node)) open = false;
  }

  function onWindowKey(event: KeyboardEvent): void {
    if (event.key === "Escape") open = false;
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<div class="dd" bind:this={root}>
  <button
    type="button"
    class="trigger"
    aria-label={label}
    aria-haspopup="listbox"
    aria-expanded={open}
    {disabled}
    onclick={() => (open = !open)}
  >
    <span class="text">{shown}</span>
    <svg
      class="caret"
      width="11"
      height="10"
      viewBox="0 0 11 10"
      aria-hidden="true"
      ><path d="M1 1.5 L5.5 8.5 L10 1.5 Z" fill="currentColor" /></svg
    >
  </button>
  {#if open}
    <ul class="menu" role="listbox" aria-label={label} bind:this={menu}>
      {#each options as option (option.value)}
        <li role="presentation">
          <button
            type="button"
            role="option"
            class="item"
            class:on={option.value === value}
            aria-selected={option.value === value}
            onclick={() => pick(option.value)}>{option.label}</button
          >
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .dd {
    position: relative;
    flex: 1;
    min-width: 0;
  }

  .trigger {
    width: 100%;
    height: var(--layout-control-h);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding: 0 var(--space-3);
    font: inherit;
    font-size: var(--font-size-sm);
    color: var(--color-md-card-text);
    background: var(--color-md-card);
    border: 1px solid var(--color-md-border);
    border-radius: 0;
    cursor: pointer;
    text-align: left;
  }

  .trigger:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .caret {
    flex: none;
  }

  .menu {
    position: absolute;
    left: 0;
    right: 0;
    top: 100%;
    z-index: 20;
    margin: 0;
    padding: 0;
    list-style: none;
    max-height: 240px;
    overflow-y: auto;
    background: var(--color-md-card);
    border: 1px solid var(--color-md-border);
    border-top: 0;
  }

  .item {
    width: 100%;
    padding: 6px var(--space-3);
    font: inherit;
    font-size: var(--font-size-sm);
    text-align: left;
    color: var(--color-md-card-text);
    background: transparent;
    border: 0;
    border-radius: 0;
    cursor: pointer;
  }

  .item:hover,
  .item:focus-visible,
  .item.on {
    background: var(--color-accent);
    color: var(--color-md-card);
    outline: none;
  }
</style>
