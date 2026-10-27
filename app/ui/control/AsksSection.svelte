<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onDestroy, onMount } from "svelte";
  import type { AskCard } from "../assistant/model";

  // Questions the assistant cannot answer alone, from every chat, in one place.
  let asks = $state<AskCard[]>([]);
  let answers = $state<Record<string, string>>({});
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setInterval> | undefined;

  async function load(): Promise<void> {
    try {
      const result = await invoke<{ asks: AskCard[] }>("sidecar_call", {
        method: "asks",
      });
      asks = result.asks;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function respond(ask: AskCard): Promise<void> {
    const text = (answers[ask.call] ?? "").trim();
    if (!text) return;
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "answer",
        params: { call: ask.call, text },
      });
      answers[ask.call] = "";
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => {
    void load();
    timer = setInterval(load, 3000);
  });
  onDestroy(() => clearInterval(timer));
</script>

<section class="control-section" aria-labelledby="control-asks">
  <h3 id="control-asks">Ask me</h3>
  <p class="hint">
    Questions the assistant is waiting on. Answer here or in its chat.
  </p>
  {#if asks.length === 0}
    <p class="muted">No questions are waiting.</p>
  {:else}
    <ul aria-label="Waiting questions">
      {#each asks as ask (ask.call)}
        <li>
          <p>{ask.question}</p>
          <div class="row">
            <input
              type="text"
              aria-label={`Answer: ${ask.question}`}
              bind:value={answers[ask.call]}
              onkeydown={(e) => e.key === "Enter" && respond(ask)}
            />
            <button type="button" class="primary" onclick={() => respond(ask)}
              >Respond</button
            >
          </div>
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
