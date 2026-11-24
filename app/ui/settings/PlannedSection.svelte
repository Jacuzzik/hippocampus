<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Features that need a service, a model download or a large design. Each is a real card with what it will do
  // and what is missing, so nothing here is a dead button. The id is the plan item it answers.
  const PLANNED = [
    {
      id: "7.18",
      name: "Built-in code editor",
      what: "A file tree, tabs, save, and git views (changes, history, branch compare).",
      reason:
        "Needs an embedded editor such as Monaco or CodeMirror. The IDE button opens the folder in VS Code.",
    },
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
      id: "7.31",
      name: "Usage statistics",
      what: "Anonymous usage events with a clear opt-out and a page that says what is sent.",
      reason:
        "Nothing is collected or sent. If it is ever added, it will be off by default and documented.",
    },
    {
      id: "N.17",
      name: "Quick capture hotkey",
      what: "A global hotkey drops a thought into an Inbox note, stamped with the time and the active agent.",
      reason:
        "Needs a global shortcut, which the operating system must allow first.",
    },
    {
      id: "N.04",
      name: "Agent trail notes",
      what: "At the end of a session each agent writes a short note into the vault: what it read, changed and decided.",
      reason:
        "Needs a line in the briefing and a check that the note exists; the briefing text is held until the owner answers.",
    },
    {
      id: "N.05",
      name: "Briefing builder with preview",
      what: "Pick the blocks of a briefing and see the exact text and its size before it is sent.",
      reason:
        "Needs the briefing split into blocks; the briefing wording is held until the owner answers.",
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
      id: "N.26",
      name: "Demo vault and first-run tour",
      what: "A labelled sample vault with a rich graph and a short guided tour.",
      reason:
        "Needs sample notes and a tour overlay designed first; not built.",
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
