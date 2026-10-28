<script lang="ts">
  import { ACCENTS, faceFor, type Accent } from "./agentCard";

  interface Props {
    name: string;
    accent: Accent;
    model: string;
    details?: string[];
  }

  let { name, accent, model, details = [] }: Props = $props();

  const faces = import.meta.glob("../assets/faces/*.png", {
    eager: true,
    query: "?url",
    import: "default",
  }) as Record<string, string>;
  const face = $derived(faces[`../assets/faces/${faceFor(name)}`]);
</script>

<section
  class="agent-card"
  aria-label="Agent {name}"
  style:--card-accent="var(--color-{accent})"
  style:--card-on="var(--color-{ACCENTS[accent].text})"
>
  <div class="face">
    <img src={face} alt="" />
  </div>
  <div class="text">
    <h2>{name}</h2>
    <p class="model">{model}</p>
    {#each details as line (line)}
      <p class="detail">{line}</p>
    {/each}
  </div>
</section>

<style>
  .agent-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--color-face-disc);
    color: var(--card-accent);
    border-radius: var(--radius-md);
  }

  .face {
    flex: none;
    width: 80px;
    height: 80px;
    display: grid;
    place-items: center;
    background: var(--color-face-disc);
    border-radius: var(--radius-md);
  }

  .face img {
    width: 100%;
    height: 100%;
  }

  .text {
    min-width: 0;
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-md);
  }

  p {
    margin: 0;
    font-size: var(--font-size-xs);
  }

  .model {
    font-family: var(--font-mono);
    overflow-wrap: anywhere;
  }
</style>
