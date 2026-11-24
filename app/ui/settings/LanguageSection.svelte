<script lang="ts">
  import Dropdown from "../controls/Dropdown.svelte";
  import {
    LANGUAGES,
    language,
    setLanguage,
    t,
    type Language,
  } from "../i18n/index.svelte.ts";
</script>

<section class="control-section" aria-labelledby="language-title">
  <h3 id="language-title">{t("Language and direction")}</h3>
  <p class="hint">
    {t(
      "Choose the language of the menus, dialogs and the tour. English is the default. Notes, agents' words and anything you wrote stay as they are.",
    )}
  </p>
  <Dropdown
    label="Language"
    value={language.id}
    options={LANGUAGES.map((l) => ({ value: l.id, label: l.label }))}
    onchange={(next) => setLanguage(next as Language)}
  />
  {#if language.id !== "en"}
    <p class="muted">
      {t(
        "Not every screen is translated yet. A phrase without a translation shows in English.",
      )}
    </p>
  {/if}
</section>
