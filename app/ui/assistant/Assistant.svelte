<script lang="ts">
  import { onMount } from "svelte";
  import Orb from "./Orb.svelte";
  import { ORB_LABELS, type ToolStatus } from "./model";
  import { assistant } from "./session.svelte";

  const STATUS_TEXT: Record<ToolStatus, string> = {
    requested: "asked",
    running: "running",
    done: "done",
    declined: "declined",
    failed: "failed",
  };

  const TIER_TEXT: Record<string, string> = {
    read: "reads",
    open: "opens",
    browse: "browses",
    write: "writes",
    act: "acts",
  };

  // shortcut: text files up to 100 KB, read in the browser and sent inline with the next message.
  const MAX_FILE_BYTES = 100_000;
  // No speech-to-text source exists in this build (no voice/ module), so voice input cannot transcribe yet.
  const NO_STT = "No speech-to-text source is set up, so voice input is not available. Type your message instead.";

  let draft = $state("");
  let answers = $state<Record<string, string>>({});
  let attached = $state<{ name: string; text: string }[]>([]);
  let fileInput = $state<HTMLInputElement>();
  let notice = $state("");
  const chat = $derived(assistant.chat);

  onMount(() => {
    void assistant.start();
  });

  async function pickFiles(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const picked = Array.from(input.files ?? []);
    input.value = "";
    for (const file of picked) {
      if (file.size > MAX_FILE_BYTES) {
        notice = `${file.name} is larger than 100 KB, so it was not attached.`;
        continue;
      }
      attached = [...attached, { name: file.name, text: await file.text() }];
    }
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    const files = attached.map(
      (file) => `Attached file: ${file.name}\n\`\`\`\n${file.text}\n\`\`\``,
    );
    const text = [...files, draft].join("\n\n");
    draft = "";
    attached = [];
    notice = "";
    void assistant.send(text);
  }

  function answer(event: SubmitEvent, call: string): void {
    event.preventDefault();
    const text = (answers[call] ?? "").trim();
    if (!text) return;
    answers[call] = "";
    void assistant.answer(call, text);
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "Escape" && assistant.busy) {
      void assistant.stop();
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

<aside class="assistant md-theme" aria-label="Assistant">

  <header class="head">
    <Orb state={chat.orb} />
    <span class="state">{ORB_LABELS[chat.orb]}</span>
    <label class="session">
      <span class="muted">Session</span>
      <select
        aria-label="Session"
        value={assistant.viewing ?? assistant.sessions.length - 1}
        onchange={(e) => assistant.showSession(Number(e.currentTarget.value))}
      >
        {#each assistant.sessions as _, i (i)}
          <option value={i}>{i === assistant.sessions.length - 1 ? "Current" : `Past ${i + 1}`}</option>
        {/each}
      </select>
    </label>
    <button type="button" class="new-session" disabled={assistant.busy} onclick={() => assistant.newSession()}>
      New session
    </button>
  </header>

  <ol class="messages" aria-live="polite" aria-label="Conversation">
    {#each chat.messages as message, index (index)}
      <li class="message {message.role}">
        <span class="who"
          >{message.role === "user"
            ? "You"
            : message.role === "assistant"
              ? "Assistant"
              : "Note"}</span
        >
        <p>{message.text}</p>
      </li>
    {/each}
  </ol>

  {#each chat.confirms as card (card.call)}
    <section class="confirm" role="group" aria-label="Approval needed">
      <p class="confirm-title">
        Approve: {card.name}
        {TIER_TEXT[card.tier] ?? card.tier}
      </p>
      <pre>{card.preview}</pre>
      <div class="actions">
        <button
          type="button"
          class="approve"
          onclick={() => assistant.decide(card.call, true)}
        >
          Approve
        </button>
        <button type="button" onclick={() => assistant.decide(card.call, false)}
          >Decline</button
        >
      </div>
    </section>
  {/each}

  {#each chat.asks as ask (ask.call)}
    <form
      class="ask"
      aria-label="Question from the assistant"
      onsubmit={(event) => answer(event, ask.call)}
    >
      <p class="confirm-title">{ask.question}</p>
      <label class="visually-hidden" for="ask-{ask.call}">Your answer</label>
      <textarea id="ask-{ask.call}" rows="2" bind:value={answers[ask.call]}
      ></textarea>
      <div class="actions">
        <button type="submit" disabled={!(answers[ask.call] ?? "").trim()}
          >Answer</button
        >
      </div>
    </form>
  {/each}

  <section class="tools" aria-label="Tool log">
    <h3 class="visually-hidden">Tool log</h3>
    {#if chat.tools.length === 0 && chat.activity.length === 0}
      <p class="muted">No tools used yet.</p>
    {/if}
    <!-- Terminal lines, as in the mockup: the provider's session echoed as $ and > prompts. -->
    <div class="term">
      <div><span class="prompt">$</span> claude</div>
      {#each chat.activity as entry, index (index)}
        <div><span class="arrow">&gt;</span> <time>{entry.at}</time> {entry.text}</div>
      {/each}
      {#each chat.tools as tool (tool.call + tool.name)}
        <div>
          <span class="arrow">&gt;</span> {tool.name}
          <span class="status">{STATUS_TEXT[tool.status]}</span>
        </div>
      {/each}
      <div><span class="prompt">$</span> _</div>
    </div>
    {#if chat.budgetPause !== null}
      <div class="budget-card" role="alert">
        <p>
          The {chat.budgetPause.scope}
          {chat.budgetPause.window} token cap is used. Allow one more request, then
          send your message again.
        </p>
        <button
          type="button"
          class="continue"
          disabled={assistant.busy}
          onclick={() => assistant.allowOne()}>Allow one more request</button
        >
      </div>
    {/if}
    {#if chat.paused !== null}
      <button
        type="button"
        class="continue"
        disabled={assistant.busy}
        onclick={() => assistant.resume()}>Continue</button
      >
    {/if}
  </section>

  <form class="composer" onsubmit={submit}>
    <span class="queue-label">Queue</span>
    <label class="visually-hidden" for="assistant-input"
      >Message the assistant</label
    >
    {#if attached.length > 0}
      <ul class="chips" aria-label="Attached files">
        {#each attached as file, index (index)}
          <li class="chip">
            <span>{file.name}</span>
            <button
              type="button"
              aria-label="Remove {file.name}"
              onclick={() => (attached = attached.filter((_, i) => i !== index))}
              >×</button
            >
          </li>
        {/each}
      </ul>
    {/if}
    <textarea
      id="assistant-input"
      rows="2"
      bind:value={draft}
      placeholder="Ask about your notes…"
      disabled={assistant.busy}></textarea>
    {#if notice}
      <p class="notice" role="status">{notice}</p>
    {/if}
    <input
      bind:this={fileInput}
      type="file"
      multiple
      accept="text/*,.md,.txt,.csv,.json"
      class="visually-hidden"
      tabindex="-1"
      aria-hidden="true"
      onchange={pickFiles}
    />
    <div class="actions">
      <button
        type="button"
        disabled={assistant.busy}
        onclick={() => fileInput?.click()}>+ files</button
      >
      <button
        type="button"
        disabled={assistant.busy}
        onclick={() => (notice = NO_STT)}>voice</button
      >
      <button
        type="submit"
        disabled={assistant.busy || (!draft.trim() && attached.length === 0)}
        >Send</button
      >
      <button
        type="button"
        class="stop"
        onclick={() => assistant.stop()}
        disabled={!assistant.busy}
        aria-keyshortcuts="Escape"
      >
        Stop
      </button>
    </div>
  </form>
</aside>

<style>
  .assistant {
    grid-area: panel;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
    padding: var(--space-4);
    background: var(--color-bg-1);
    border-left: 1px solid var(--color-border);
    color: var(--color-text);
    overflow-y: auto;
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    font-weight: 600;
  }

  .state,
  .muted {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .state {
    margin-left: auto;
  }

  .messages {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .message p {
    margin: 0;
    white-space: pre-wrap;
  }

  .who {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
  }

  .message.error p {
    color: var(--color-danger);
  }

  .confirm,
  .ask {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-confirm);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .confirm-title {
    margin: 0;
    font-weight: 600;
  }

  pre {
    margin: 0;
    max-height: 12rem;
    overflow: auto;
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--color-bg-0);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    white-space: pre-wrap;
  }

  .term {
    font-size: var(--font-size-xs);
    line-height: 1.5;
    color: var(--color-md-text-muted);
    overflow-wrap: anywhere;
  }

  .prompt {
    color: var(--color-md-confirm);
  }

  .arrow {
    color: var(--color-md-text-subtle);
  }

  .term {
    font-size: var(--term-size, var(--font-size-xs));
  }

  .queue-label {
    display: block;
    font-family: "Press Start 2P", monospace;
    font-size: 7px;
    color: var(--color-md-text-muted);
    margin-bottom: var(--space-1);
  }

  .term time {
    color: var(--color-md-text-subtle);
  }

  .continue {
    align-self: flex-start;
    font: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  .tier {
    padding: 0 var(--space-1);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .tier.write,
  .tier.act {
    border-color: var(--color-confirm);
    color: var(--color-confirm);
  }

  .status {
    margin-left: auto;
    color: var(--color-text-muted);
  }

  .composer {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    max-width: 100%;
    padding: 0 var(--space-1) 0 var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    font-size: 0.85em;
  }

  .chip span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chip button {
    padding: 0 var(--space-1);
    border: none;
    background: none;
    line-height: 1;
  }

  .notice {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.85em;
  }

  textarea {
    resize: vertical;
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-0);
    color: var(--color-text);
    font: inherit;
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }

  button {
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    color: var(--color-text);
    font: inherit;
    cursor: pointer;
  }

  button:focus-visible,
  textarea:focus-visible {
    outline: 2px solid var(--color-text);
    outline-offset: 2px;
  }

  button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .approve {
    background: var(--color-accent);
    border-color: var(--color-accent);
    color: var(--color-accent-on);
  }

  .stop:not(:disabled) {
    border-color: var(--color-danger);
    color: var(--color-danger);
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
</style>
