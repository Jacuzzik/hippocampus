<script lang="ts">
  // The design tokens, read from the generated tokens.css itself, so this page cannot drift from the app.
  import tokensCss from "../styles/tokens.css?raw";

  type Token = { name: string; value: string };

  // Only the first :root block: the dark theme, which holds every token. Later blocks override a few for light.
  const block = tokensCss.slice(0, tokensCss.indexOf("}"));
  const tokens: Token[] = [
    ...block.matchAll(/^\s*(--[\w-]+):\s*(.+?);\s*$/gm),
  ].map((m) => ({ name: m[1] ?? "", value: m[2] ?? "" }));

  const GROUPS: { title: string; prefix: string }[] = [
    { title: "Colour", prefix: "--color-" },
    { title: "Type", prefix: "--font-" },
    { title: "Spacing", prefix: "--space-" },
    { title: "Radius", prefix: "--radius-" },
    { title: "Motion", prefix: "--duration-" },
    { title: "Motion curve", prefix: "--ease-" },
    { title: "Layout", prefix: "--layout-" },
  ];

  const grouped = GROUPS.map((group) => ({
    ...group,
    rows: tokens.filter((t) => t.name.startsWith(group.prefix)),
  })).filter((group) => group.rows.length > 0);
</script>

<section class="control-section" aria-label="Design tokens">
  <h3>Design tokens</h3>
  <p class="hint">
    Every colour, size and duration the app uses. This list is read from the
    generated token file, so it matches what is on screen. Values shown are for
    the dark theme.
  </p>
  {#each grouped as group (group.prefix)}
    <h4>{group.title}</h4>
    <ul class="tokens" aria-label={group.title}>
      {#each group.rows as token (token.name)}
        <li>
          {#if group.prefix === "--color-"}
            <span class="swatch" style:background={`var(${token.name})`}></span>
          {/if}
          <code>{token.name}</code>
          <span class="value">{token.value}</span>
        </li>
      {/each}
    </ul>
  {/each}
</section>

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--font-size-sm);
  }

  .tokens {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    font-size: var(--font-size-xs);
  }

  .swatch {
    flex: none;
    width: var(--space-4);
    height: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .value {
    margin-left: auto;
    color: var(--color-text-muted);
  }
</style>
