<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

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

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-jobs">
  <h3 id="control-jobs">Scheduled notes jobs</h3>
  <p class="hint">
    {on} of {jobs.length} on. A job runs when it is due and reports its result to
    the activity log.
  </p>
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
      </li>
    {/each}
  </ul>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
