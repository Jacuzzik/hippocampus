<script lang="ts">
  // Teams are shared agents across people. Nobody is enrolled in this build.
  let message = $state<string | null>(null);

  function start(): void {
    message =
      "Not set up: teams need the team service, which this build does not include.";
  }
</script>

<section class="control-section" aria-labelledby="control-teams">
  <h3 id="control-teams">Teams</h3>
  <p class="hint">Share agents with other people. Nothing is enrolled yet.</p>
  <p class="muted">Status: Not enrolled</p>
  <div class="row">
    <button type="button" onclick={start}>Start a team</button>
  </div>
  {#if message}<p class="error" role="status">{message}</p>{/if}
</section>
