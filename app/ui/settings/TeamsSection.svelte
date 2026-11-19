<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Teams are shared agents across people. The team service is not part of this build.
</script>

<section class="control-section" aria-labelledby="control-teams">
  <h3 id="control-teams">Teams</h3>
  <StatusCard
    name="Share agents with other people"
    what="A team sees the same agents, tasks and notes, each person with their own sign-in."
    status="Planned"
    reason="Teams need a team service, which this build does not include. Nobody is enrolled."
  />
</section>
