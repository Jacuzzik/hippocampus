<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Features that need a service, a model download or a large design. Each is a real card with what it will do
  // and what is missing, so nothing here is a dead button. The id is the plan item it answers.
  const PLANNED = [
    {
      id: "7.25",
      name: "Slack bot",
      what: "One bot that answers in chosen channels and direct messages and replies in threads.",
      reason: "Needs a token store and a message bridge. See Connectors.",
    },
    {
      id: "7.27",
      name: "Dictation by hotkey",
      what: "Speak into any app with a speech model that ships with Hippocampus.",
      reason: "Needs a bundled speech-to-text model and a global hotkey.",
    },
    {
      id: "7.30",
      name: "Languages",
      what: "English, Simplified Chinese and Arabic (right to left) interfaces.",
      reason:
        "Needs every screen's text moved into one catalogue first (H.02), then a right-to-left layout (H.03).",
    },
    {
      id: "N.12",
      name: "Approvals with the exact command and diff",
      what: "A risky request shows the command or file change, with approve once, approve for this folder, or deny.",
      reason:
        "Needs the shell sandbox to report each request; the sandbox is finished work and is not changed here.",
    },
    {
      id: "N.15",
      name: "Split terminals",
      what: "Two agent terminals, or a terminal and a note, side by side.",
      reason:
        "Needs a second live terminal in the right panel; the one terminal component is finished work and is not changed here.",
    },
    {
      id: "7.07",
      name: "Several vaults in separate windows",
      what: "Open another vault with its own folder, agents and memory in a second window.",
      reason:
        "Needs multi-window support in the shell; the vault switch inside one window works.",
    },
    {
      id: "D.07",
      name: "Teams",
      what: "A team sees the same agents, tasks and notes, each person with their own sign-in.",
      reason: "Needs a team service, which this build does not include.",
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
