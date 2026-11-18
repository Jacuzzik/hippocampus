<script lang="ts">
  import StatusCard from "../controls/StatusCard.svelte";

  // Password links are made on the user's account (14.04): from a note in the graph, with its Share button.
</script>

<section class="control-section" aria-labelledby="control-share">
  <h3 id="control-share">Sharing</h3>
  <StatusCard
    name="Share a note by password link"
    what="A link to one note that asks for a password and stops working after a time you choose, 60 minutes by default."
    status="Needs setup"
    reason="Sign in under General > Account, then open a note in the graph and press Share. Your links are listed under Account."
  />
</section>
