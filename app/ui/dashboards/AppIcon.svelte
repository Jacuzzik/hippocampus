<script lang="ts">
  // One icon per connected app, a 24px line drawing of what the service is for (not its logo).
  // An app with no drawing here, such as a custom connector, gets the plug.
  let { id }: { id: string } = $props();
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
  {#if id === "shopify"}
    <!-- a shopping bag -->
    <path d="M5 8h14l-1 12H6z" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
  {:else if id === "builtbybit"}
    <!-- a block -->
    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
    <path d="M4 7.5l8 4.5 8-4.5M12 12v9" />
  {:else if id === "stripe"}
    <!-- a card -->
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M3 10h18M7 15h4" />
  {:else if id === "github"}
    <!-- code -->
    <path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 6l-3 12" />
  {:else if id === "gitlab"}
    <!-- a merge -->
    <circle cx="6" cy="6" r="2" />
    <circle cx="6" cy="18" r="2" />
    <circle cx="18" cy="12" r="2" />
    <path d="M6 8v8M6 8c0 4 6 4 10 4" />
  {:else if id === "vercel"}
    <!-- a deploy triangle -->
    <path d="M12 4l9 16H3z" />
  {:else if id === "netlify"}
    <!-- a site grid -->
    <path d="M12 3l9 9-9 9-9-9z" />
    <path d="M12 8v8M8 12h8" />
  {:else if id === "cloudflare"}
    <!-- a cloud -->
    <path
      d="M7 18h10a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.5 1.5A3.3 3.3 0 0 0 7 18z"
    />
  {:else if id === "plausible"}
    <!-- visitors: bars -->
    <path d="M5 20v-6M10 20V8M15 20v-9M20 20V4" />
  {:else if id === "posthog"}
    <!-- a funnel -->
    <path d="M4 5h16l-6 7v6l-4 2v-8z" />
  {:else if id === "sentry"}
    <!-- an error -->
    <path d="M12 4l9 16H3z" />
    <path d="M12 10v4M12 17v.5" />
  {:else if id === "airtable"}
    <!-- a table -->
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 10h18M3 14.5h18M9 10v9" />
  {:else if id === "discord"}
    <!-- a chat -->
    <path d="M4 6h16v10H10l-4 3v-3H4z" />
    <path d="M9 11v.5M15 11v.5" />
  {:else if id === "telegram"}
    <!-- a paper plane -->
    <path d="M21 4L3 11l6 2 2 6 3-4 4 3z" />
    <path d="M9 13l8-6" />
  {:else if id === "lemonsqueezy"}
    <!-- a lemon slice -->
    <circle cx="12" cy="12" r="8" />
    <path d="M12 4v16M4 12h16M6.5 6.5l11 11M17.5 6.5l-11 11" />
  {:else if id === "gumroad"}
    <!-- a price tag -->
    <path d="M3 12V4h8l10 10-8 8z" />
    <circle cx="7.5" cy="8" r="1.2" />
  {:else if id === "paddle"}
    <!-- a receipt -->
    <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
    <path d="M9 8h6M9 12h6" />
  {:else if id === "woocommerce"}
    <!-- a cart -->
    <path d="M3 4h2l2 11h11l2-8H6" />
    <circle cx="9" cy="19" r="1.3" />
    <circle cx="17" cy="19" r="1.3" />
  {:else if id === "modrinth"}
    <!-- a mod: a wrench -->
    <path
      d="M15 4a4 4 0 0 0-4.5 5.5L4 16l4 4 6.5-6.5A4 4 0 0 0 20 9l-3 1-2-2z"
    />
  {:else if id === "polar"}
    <!-- a star -->
    <path
      d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z"
    />
  {:else if id === "youtube"}
    <!-- a video -->
    <rect x="3" y="6" width="18" height="12" rx="3" />
    <path d="M10 9.5v5l4.5-2.5z" />
  {:else if id === "todoist"}
    <!-- a checklist -->
    <path d="M4 7l1.5 1.5L8 6M4 13l1.5 1.5L8 12M11 7h9M11 13h9M11 18h9" />
  {:else}
    <!-- a plug: a custom connector, or any app without its own drawing -->
    <path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4" />
  {/if}
</svg>
