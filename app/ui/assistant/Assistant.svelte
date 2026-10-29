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

  let draft = $state("");
  let answers = $state<Record<string, string>>({});
  const chat = $derived(assistant.chat);

  onMount(() => {
    void assistant.start();
  });

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    const text = draft;
    draft = "";
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
    <label class="visually-hidden" for="assistant-input"
      >Message the assistant</label
    >
    <textarea
      id="assistant-input"
      rows="2"
      bind:value={draft}
      placeholder="Ask about your notes…"
      disabled={assistant.busy}></textarea>
    <div class="actions">
      <button type="submit" disabled={assistant.busy || !draft.trim()}
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
