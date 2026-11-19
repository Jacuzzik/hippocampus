<script lang="ts">
  import ErrorRow from "../controls/ErrorRow.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Loading from "../controls/Loading.svelte";

  // Repeating jobs over the notes. Each runs when it is due, about once a minute is checked.
  type Job = {
    id: string;
    name: string;
    kind: string;
    every_days: number;
    enabled: boolean;
    last_run: string | null;
  };

  let jobs = $state<Job[]>([]);
  let error = $state<string | null>(null);
  const on = $derived(jobs.filter((job) => job.enabled).length);

  async function load(): Promise<void> {
    try {
      jobs = (await invoke<{ jobs: Job[] }>("sidecar_call", { method: "jobs" }))
        .jobs;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function update(
    job: Job,
    enabled: boolean,
    everyDays: number,
  ): Promise<void> {
    error = null;
    try {
      const result = await invoke<{ jobs: Job[] }>("sidecar_call", {
        method: "set_job",
        params: { id: job.id, enabled, every_days: everyDays },
      });
      jobs = result.jobs;
    } catch (cause) {
      error = String(cause);
      await load();
    }
  }

  // Run now runs the job once, due or not. The click is the user's approval.
  let ran = $state<{ id: string; text: string } | null>(null);
  async function runNow(job: Job): Promise<void> {
    error = null;
    ran = null;
    try {
      const result = await invoke<{ jobs: Job[]; result: string }>(
        "sidecar_call",
        { method: "run_job", params: { id: job.id, approve: true } },
      );
      jobs = result.jobs;
      ran = { id: job.id, text: result.result };
    } catch (cause) {
      error = String(cause);
    }
  }

  // False until the first answer, so the loader shows and an empty list is not claimed too early.
  let loaded = $state(false);
  onMount(() => void load().finally(() => (loaded = true)));
</script>

<section class="control-section" aria-labelledby="control-jobs">
  <h3 id="control-jobs">Scheduled notes jobs</h3>
  <p class="hint">
    {on} of {jobs.length} on. A job runs when it is due and reports its result to
    the activity log.
  </p>
  {#if !loaded}<Loading what="the scheduled jobs" rows={1} />{/if}
  <ul aria-label="Scheduled jobs">
    {#each jobs as job (job.id)}
      <li class="row">
        <label>
          <input
            type="checkbox"
            checked={job.enabled}
            onchange={(e) =>
              update(job, e.currentTarget.checked, job.every_days)}
          />
          {job.name}
        </label>
        <label>
          every
          <input
            type="text"
            inputmode="numeric"
            size="3"
            aria-label={`${job.name} interval in days`}
            value={String(job.every_days)}
            onchange={(e) => {
              const days = Number(e.currentTarget.value);
              if (Number.isInteger(days) && days >= 1)
                void update(job, job.enabled, days);
              else e.currentTarget.value = String(job.every_days);
            }}
          />
          days
        </label>
        <span class="muted"
          >{job.last_run
            ? `last ${job.last_run.slice(0, 16).replace("T", " ")}`
            : "not run yet"}</span
        >
        <button
          type="button"
          class="run"
          aria-label={`Run ${job.name} now`}
          onclick={() => void runNow(job)}>Run now</button
        >
        {#if ran?.id === job.id}
          <p class="muted" role="status">{ran.text}</p>
        {/if}
      </li>
    {/each}
  </ul>
  {#if error}<ErrorRow message={error} onretry={load} />{/if}
</section>

<style>
  .run {
    font: inherit;
    color: inherit;
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }
</style>
