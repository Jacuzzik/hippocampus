<script lang="ts">
  // N.17: Ctrl+Shift+Space drops a thought into the vault's Inbox note, stamped with the time and the selected agent.
  import Dialog from "../controls/Dialog.svelte";
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { addedAgents, selection } from "../owner/addedAgents.svelte.ts";

  let { onclose, global }: { onclose: () => void; global: boolean | null } =
    $props();
  let text = $state("");
  let error = $state("");
  let busy = $state(false);
  let input: HTMLTextAreaElement | undefined = $state();
  $effect(() => input?.focus());
  const agent = $derived(
    addedAgents.list.find((a) => a.id === selection.id)?.name ?? "",
  );

  async function keep(): Promise<void> {
    if (busy) return;
    busy = true;
    error = "";
    try {
      await invoke("sidecar_call", {
        method: "capture",
        params: { text, agent },
      });
      onclose();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
</script>

<Dialog title="Quick capture" {onclose}>
  <form
    onsubmit={(e) => {
      e.preventDefault();
      void keep();
    }}
  >
    <textarea
      bind:this={input}
      bind:value={text}
      rows="3"
      aria-label="Thought"
      placeholder="A thought to keep"
      onkeydown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          void keep();
        }
      }}></textarea>
    <p class="hint">
      Goes to the Inbox note{agent ? `, marked ${agent}` : ""}. Enter keeps it.
      {#if global !== true}Ctrl+Shift+Space works while this window is in front:
        this desktop does not let an app take a key everywhere.{/if}
    </p>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <Button type="submit" variant="primary" disabled={busy || !text.trim()}
      >Keep</Button
    >
  </form>
</Dialog>

<style>
  textarea {
    width: 100%;
    box-sizing: border-box;
    font: inherit;
  }
</style>
