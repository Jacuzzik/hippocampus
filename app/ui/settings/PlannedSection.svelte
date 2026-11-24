<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Features that need a service, a model download or a large design. Each is a real card with what it will do
  // and what is missing, so nothing here is a dead button. The id is the plan item it answers.
  const PLANNED = [
    {
      id: "N.15",
      name: "Split terminals",
      what: "Two agent terminals, or a terminal and a note, side by side.",
      reason:
        "Needs a second live terminal in the right panel; the one terminal component is finished work and is not changed here.",
    },
  ] as const;
</script>

<section class="control-section" aria-labelledby="planned-title">
  <h3 id="planned-title">Planned features</h3>
  <p class="hint">
    Not built yet. Each one says what it will do and what is missing. None of
    them sends anything anywhere.
  </p>
  <div class="grid">
    {#each PLANNED as item (item.name)}
      <StatusCard
        name={item.name}
        what={item.what}
        status="Planned"
        reason={item.reason}
      />
    {/each}
  </div>
</section>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
</style>
