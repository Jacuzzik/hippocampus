<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Features that need a service, a model download or a large design. Each is a real card with what it will do
  // and what is missing, so nothing here is a dead button. The id is the plan item it answers.
  const PLANNED = [
    {
      id: "7.06",
      name: "A git worktree per agent",
      what: "Agents working in parallel get their own branch folder, so they do not collide.",
      reason:
        "Needs a worktree created on start and removed on archive; not built.",
    },
    {
      id: "7.09",
      name: "Search memory by meaning",
      what: "Finds notes by what they mean, not only by their words.",
      reason:
        "Needs a local embedding model (Ollama or a small model); none is installed.",
    },
    {
      id: "7.11",
      name: "One committer for shared files",
      what: "Only the app commits shared files, so agents never fight over the git index.",
      reason: "Needs a commit queue in the backend; not built.",
    },
    {
      id: "7.18",
      name: "Built-in code editor",
      what: "A file tree, tabs, save, and git views (changes, history, branch compare).",
      reason:
        "Needs an embedded editor such as Monaco or CodeMirror. The IDE button opens the folder in VS Code.",
    },
    {
      id: "7.21",
      name: "Circuit breaker",
      what: "Steers, then constrains, then stops an agent that loops, errors again and again or overspends.",
      reason:
        "Needs a watcher on tokens, repeats and errors; only the kill switch and budgets exist.",
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
      id: "N.01",
      name: "One search box for everything",
      what: "Ctrl+K across notes, agent memory, inbox, history and cards, with the source of every hit.",
      reason:
        "Needs one index in the backend; notes search exists, the rest does not.",
    },
    {
      id: "N.09",
      name: "Daily brief note",
      what: "Each morning a Today note: open cards, waiting questions, agent states and yesterday's work.",
      reason:
        "Needs a scheduled job and a template; off by default when built.",
    },
    {
      id: "N.11",
      name: "Session replay",
      what: "Scrub a past agent session like a recording, text only, and jump to its tool calls.",
      reason:
        "Needs sessions stored with timestamps and a size cap; History and Traces show the events today.",
    },
    {
      id: "N.17",
      name: "Quick capture hotkey",
      what: "A global hotkey drops a thought into an Inbox note, stamped with the time and the active agent.",
      reason:
        "Needs a global shortcut, which the operating system must allow first.",
    },
    {
      id: "N.21",
      name: "Note history",
      what: "Per-note history with a diff view and restore.",
      reason: "Needs a snapshot on every save, keeping the last 20.",
    },
    {
      id: "N.22",
      name: "Playbooks",
      what: "Named workflows, such as 'review this folder', that send a briefing and create cards.",
      reason: "Needs a note format for a playbook and a runner.",
    },
    {
      id: "G.04",
      name: "Update check and what's new",
      what: "Tells you when a new version is out and shows its changelog.",
      reason:
        "Checking means a call to a release server, and the app calls out only to your model provider. Until you allow it, get new versions from the Download page.",
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
    {#each PLANNED as item (item.id)}
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
