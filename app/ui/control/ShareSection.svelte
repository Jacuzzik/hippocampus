<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  // Password links for one note, 60 minutes by default. Links need a share host, which is not
  // set up yet, so making one reports "Not set up".
  let password = $state("");
  let minutes = $state("60");
  let message = $state<string | null>(null);
  let error = $state<string | null>(null);

  async function link(): Promise<void> {
    error = null;
    message = null;
    try {
      await invoke("sidecar_call", {
        method: "share",
        params: { password, minutes: Number(minutes) },
      });
      message = "Link made.";
    } catch (cause) {
      error = String(cause);
    }
  }
</script>

<section class="control-section" aria-labelledby="control-share">
  <h3 id="control-share">
    Share a note by password link <span class="badge">Not set up</span>
  </h3>
  <p class="hint">
    The link expires after the minutes you choose, 60 by default. The password
    must be at least 8 characters. No share host is set up in this app yet.
  </p>
  <form
    class="row"
    onsubmit={(e) => {
      e.preventDefault();
      void link();
    }}
  >
    <input
      type="password"
      aria-label="Link password"
      autocomplete="new-password"
      bind:value={password}
    />
    <label>
      minutes
      <input type="text" inputmode="numeric" size="4" bind:value={minutes} />
    </label>
    <button type="submit" disabled={password.length < 8}>Make link</button>
  </form>
  {#if message}<p class="muted">{message}</p>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
