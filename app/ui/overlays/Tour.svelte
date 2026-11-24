<script lang="ts">
  // N.26: a short guided tour on the first start, and from Settings at any time. Skipping is always one click.
  import Dialog from "../controls/Dialog.svelte";
  import Button from "../controls/Button.svelte";
  import { t, tf } from "../i18n/index.svelte.ts";

  let { onclose, ondemo }: { onclose: () => void; ondemo: () => void } =
    $props();

  const STEPS = [
    {
      title: "Your notes, as a graph",
      text: "Each dot is a note and each line is a link between two notes. Click a dot to read the note; drag the background to look around.",
    },
    {
      title: "Agents in the right panel",
      text: "Add an agent, give it a task, and watch its terminal. Agents read and write the same notes you do.",
    },
    {
      title: "Search and quick capture",
      text: "Ctrl+K opens the command box, and Ctrl+Shift+Space keeps a thought in the Inbox note from any window.",
    },
    {
      title: "Settings",
      text: "Models and keys, the network setting, budgets and everything optional live in Settings. Nothing leaves this computer until you allow it.",
    },
    {
      title: "Try the demo vault",
      text: "A small labelled sample vault shows a rich graph with no risk to your own notes. You can go back to your vault from Settings, General.",
    },
  ] as const;

  let step = $state(0);
  const last = $derived(step === STEPS.length - 1);
  const now = $derived(STEPS[step] ?? STEPS[0]);
</script>

<Dialog title={t("Tour")} heading={t(now.title)} {onclose} center dim>
  <p class="count">{tf("Step {n} of {m}", { n: step + 1, m: STEPS.length })}</p>
  <p>{t(now.text)}</p>
  <div class="row">
    <Button onclick={onclose}>{t("Skip the tour")}</Button>
    <span class="grow"></span>
    {#if step > 0}<Button onclick={() => step--}>{t("Back")}</Button>{/if}
    {#if last}
      <Button onclick={ondemo}>{t("Open the demo vault")}</Button>
      <Button onclick={onclose}>{t("Done")}</Button>
    {:else}
      <Button onclick={() => step++}>{t("Next")}</Button>
    {/if}
  </div>
</Dialog>

<style>
  .count {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-3);
  }
  .grow {
    flex: 1;
  }
</style>
