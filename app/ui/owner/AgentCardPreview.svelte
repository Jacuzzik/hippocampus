<script lang="ts">
  // The added-agent card as the bottom bar draws it (same look and rules as AgentBar's card), without the buttons.
  // The Add agent dialog shows it while the agent is being built. Keep the styles in step with AgentBar.
  let {
    name,
    face,
    provider,
    logo,
    model,
    cmd,
  }: {
    name: string;
    face: string;
    provider: string;
    logo?: string;
    model: string;
    cmd: string;
  } = $props();
</script>

<div class="chip main added preview" aria-hidden="true">
  <img src={face} alt="" class="face" />
  <span class="text">
    <span class="head"><b>{name}</b></span>
    <span class="row">
      <span class="val provider-line">
        {#if logo}<span class="provider-logo" style:--logo={`url("${logo}")`}></span>{/if}
        <span>{provider}</span>
      </span>
    </span>
    <span class="row">
      <span class="val model">{model || "No model set"}</span>
    </span>
    <span class="row wide cmd-row">
      <span class="val cmd">{cmd || "No command yet"}</span>
    </span>
    <span class="row wide">
      <span class="ctx-bar"><span class="ctx-fill" style="width: 0%"></span></span>
      <span class="pct">—</span>
    </span>
  </span>
</div>

<style>
  .chip {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    flex: none;
    width: var(--size-320);
    min-height: 0;
    padding: 8px 12px 8px;
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--hippo-purple);
    border-top-width: 8px;
    border-radius: 0 0 2px 2px;
    font-family: var(--font-ui);
    white-space: nowrap;
    --hippo-purple: var(--color-accent);
  }

  .face {
    width: var(--size-52);
    height: var(--size-52);
    margin-top: 4px;
    object-fit: contain;
    flex: none;
  }

  .text {
    flex: 1;
    min-width: 0;
    display: block;
  }

  b {
    font-size: var(--font-size-lg);
    font-weight: 700;
    line-height: 1.2;
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .provider-line {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .provider-logo {
    width: var(--size-12);
    height: var(--size-12);
    flex: none;
    background: currentColor;
    -webkit-mask-image: var(--logo);
    mask-image: var(--logo);
    -webkit-mask-size: contain;
    mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-position: center;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--font-size-xs);
    line-height: 1.6;
  }

  .row.wide {
    margin-left: calc(-52px - var(--space-2));
    margin-right: -12px;
  }

  .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .model {
    position: relative;
    top: -2px;
  }

  .cmd-row {
    margin-right: 0;
  }

  .cmd {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    align-self: flex-start;
    padding: 1px 4px;
    line-height: 1.4;
    border-radius: var(--radius-sm);
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-weight: 700;
  }

  .ctx-bar {
    flex: 1;
    min-width: var(--size-140);
    height: 5px;
    border-radius: var(--radius-sm);
    background: var(--color-ctx-track);
    overflow: hidden;
  }

  .ctx-fill {
    display: block;
    height: 100%;
    background: var(--hippo-purple);
  }

  .pct {
    margin-left: 4px;
    font-size: var(--font-size-tag);
    color: var(--color-md-card-muted);
  }
</style>
