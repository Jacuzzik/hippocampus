<script lang="ts">
  // One icon per dashboard: a 24px line drawing in the current colour.
  let { name }: { name: string } = $props();
</script>

<svg
  viewBox="0 0 24 24"
  width="20"
  height="20"
  aria-hidden="true"
  fill="none"
  stroke="currentColor"
  stroke-width="1.6"
  stroke-linecap="round"
  stroke-linejoin="round"
>
  {#if name === "graph"}
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="7" r="2.5" />
    <circle cx="12" cy="18" r="2.5" />
    <path d="M8.2 7.2l7.6-.4M7.4 8.2l3.8 7.6M16.4 9.2l-3.3 6.8" />
  {:else if name === "apps"}
    <rect x="3.5" y="3.5" width="7" height="7" rx="1" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="1" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="1" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="1" />
  {:else if name === "providers"}
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c.6-3.4 3.2-5.5 6.5-5.5s5.9 2.1 6.5 5.5" />
    <path d="M16 4.6a3.5 3.5 0 010 6.8M18 14.7c1.9.8 3 2.7 3.5 5.3" />
  {:else if name === "finance"}
    <circle cx="12" cy="12" r="8.5" />
    <path
      d="M14.8 9.2c-.5-1-1.6-1.6-2.8-1.6-1.6 0-2.8.9-2.8 2.1 0 2.9 5.8 1.5 5.8 4.5 0 1.2-1.2 2.2-3 2.2-1.3 0-2.5-.6-3-1.7M12 6v1.6M12 16.4V18"
    />
  {:else if name === "vault"}
    <path d="M6 3.5h8l4 4v13H6z" />
    <path d="M9 11.5h6M9 15h6" />
  {:else if name === "system"}
    <rect x="6" y="6" width="12" height="12" rx="1.5" />
    <rect x="9.5" y="9.5" width="5" height="5" />
    <path
      d="M9 2.5v3.5M15 2.5v3.5M9 18v3.5M15 18v3.5M2.5 9h3.5M2.5 15h3.5M18 9h3.5M18 15h3.5"
    />
  {:else if name === "activity"}
    <path d="M2.5 12h4l2.5-6 4 12 2.5-6h6" />
  {:else if name === "github"}
    <circle cx="6" cy="5.5" r="2" />
    <circle cx="6" cy="18.5" r="2" />
    <circle cx="18" cy="6.5" r="2" />
    <path d="M6 7.5v9M18 8.5c0 6-12 3-12 8" />
  {:else if name === "calendar"}
    <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  {:else if name === "phone"}
    <rect x="7" y="2.5" width="10" height="19" rx="2" />
    <path d="M11 18.5h2" />
  {:else}
    <path d="M9 3v5M15 3v5M7 8h10v3a5 5 0 01-10 0zM12 16v5" />
  {/if}
</svg>
