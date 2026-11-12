<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Password links need a share host, which this build does not have. The card says so, in place of a
  // form that could only fail.
</script>

<section class="control-section" aria-labelledby="control-share">
  <h3 id="control-share">Sharing</h3>
  <StatusCard
    name="Share a note by password link"
    what="A link to one note that asks for a password and stops working after a time you choose, 60 minutes by default."
    status="Planned"
    reason="No share host is set up in this build, so no link can be made yet."
  />
</section>
