# Design tokens

Generated from `design/tokens.json` by `app/scripts/build-design-doc.mjs`. Do not edit by hand: run `npm run tokens` in `app/`.
Components use these variables and nothing else: `npm test` fails on a raw colour or font in a component.

## Colour (dark, the default)

| Variable | Value |
|---|---|
| `--color-bg-0` | `#222229` |
| `--color-bg-1` | `#2A2A33` |
| `--color-border` | `#333333` |
| `--color-surface` | `#222229` |
| `--color-md-bg-0` | `#222229` |
| `--color-md-bg-1` | `#222229` |
| `--color-md-surface` | `#222229` |
| `--color-md-text` | `#DADADA` |
| `--color-md-text-muted` | `#999999` |
| `--color-md-text-subtle` | `#8C8C8C` |
| `--color-md-border` | `#333333` |
| `--color-md-accent` | `#9482D3` |
| `--color-md-accent-on` | `#222229` |
| `--color-md-confirm` | `#DCAB3C` |
| `--color-md-danger` | `#D96A62` |
| `--color-md-shadow` | `rgba(26, 19, 32, 0.14)` |
| `--color-md-card` | `#FFFDF5` |
| `--color-md-card-text` | `#1A1320` |
| `--color-md-card-muted` | `#6B5878` |
| `--color-accent` | `#9482D3` |
| `--color-accent-on` | `#222229` |
| `--color-focus-ring` | `rgba(148, 130, 211, 0.55)` |
| `--color-think` | `#A896E3` |
| `--color-link` | `#A896E3` |
| `--color-confirm` | `#DCAB3C` |
| `--color-danger` | `#E08C82` |
| `--color-pending` | `#E8924A` |
| `--color-success` | `#7BC47F` |
| `--color-on-strong` | `#FFFFFF` |
| `--color-void` | `#000000` |
| `--color-scrim` | `rgba(0, 0, 0, 0.6)` |
| `--color-scrim-soft` | `rgba(20, 20, 26, 0.35)` |
| `--color-shadow-strong` | `rgba(0, 0, 0, 0.5)` |
| `--color-holo-0` | `#FFFFFF` |
| `--color-holo-1` | `#8B5CF6` |
| `--color-holo-2` | `#9D4DFF` |
| `--color-holo-3` | `#FF2FD6` |
| `--color-holo-4` | `#2F9BFF` |
| `--color-holo-5` | `#426BFF` |
| `--color-holo-6` | `#FF8A36` |
| `--color-holo-7` | `#FFE66D` |
| `--color-text` | `#DADADA` |
| `--color-text-muted` | `#999999` |
| `--color-text-subtle` | `#8C8C8C` |
| `--color-face-disc` | `#FFFFFF` |
| `--color-ds-bg` | `#222229` |
| `--color-ds-surface` | `#222229` |
| `--color-ds-elevated` | `#2A2A33` |
| `--color-ds-line` | `#333333` |
| `--color-ds-fg` | `#DADADA` |
| `--color-ds-fg2` | `#999999` |
| `--color-ds-fg-muted` | `#8C8C8C` |
| `--color-ds-accent` | `#9482D3` |
| `--color-ctx-track` | `#C4C4C4` |
| `--color-ds-accent-soft` | `rgba(148, 130, 211, 0.18)` |
| `--color-ds-btn` | `#9482D3` |
| `--color-ds-success` | `#7BC47F` |
| `--color-ds-warning` | `#DCAB3C` |
| `--color-ds-danger` | `#D96A62` |
| `--color-ds-info` | `#7FC4E8` |
| `--color-ds-chart` | `#A896E3` |
| `--color-ds-chart2` | `#E2CC55` |
| `--color-ds-chart3` | `#8B7CF0` |
| `--color-ds-grid` | `#3A3A44` |
| `--color-graph-1` | `#A896E3` |
| `--color-graph-2` | `#E2CC55` |
| `--color-graph-3` | `#8B7CF0` |
| `--color-graph-4` | `#7FC4E8` |
| `--color-graph-5` | `#8FD16F` |
| `--color-graph-6` | `#E9A657` |
| `--color-graph-7` | `#E07BB0` |
| `--color-graph-8` | `#5FD0C0` |
| `--color-ascii-bg` | `#000000` |
| `--color-ascii-node` | `#B8B8B8` |
| `--color-ascii-link` | `#4A4A4A` |
| `--color-ascii-link-hub` | `#2C2C2C` |
| `--color-ascii-label` | `#DDDDDD` |

## Colour (light theme, only what differs)

| Variable | Value |
|---|---|
| `--color-bg-0` | `#F6F5F9` |
| `--color-bg-1` | `#ECEAF2` |
| `--color-border` | `#CFCBDB` |
| `--color-surface` | `#FFFFFF` |
| `--color-md-bg-0` | `#F6F5F9` |
| `--color-md-bg-1` | `#F6F5F9` |
| `--color-md-surface` | `#FFFFFF` |
| `--color-md-text` | `#1F1B2A` |
| `--color-md-text-muted` | `#5A5468` |
| `--color-md-text-subtle` | `#6B6579` |
| `--color-md-border` | `#CFCBDB` |
| `--color-md-accent` | `#6A55C2` |
| `--color-md-accent-on` | `#FFFFFF` |
| `--color-md-confirm` | `#7A5708` |
| `--color-md-danger` | `#B3362B` |
| `--color-accent` | `#6A55C2` |
| `--color-accent-on` | `#FFFFFF` |
| `--color-focus-ring` | `rgba(106, 85, 194, 0.6)` |
| `--color-think` | `#5B46B5` |
| `--color-link` | `#5B46B5` |
| `--color-confirm` | `#7A5708` |
| `--color-danger` | `#B3362B` |
| `--color-pending` | `#94500F` |
| `--color-success` | `#256B29` |
| `--color-shadow-strong` | `rgba(31, 27, 42, 0.25)` |
| `--color-text` | `#1F1B2A` |
| `--color-text-muted` | `#5A5468` |
| `--color-text-subtle` | `#6B6579` |
| `--color-ds-bg` | `#F6F5F9` |
| `--color-ds-surface` | `#FFFFFF` |
| `--color-ds-elevated` | `#ECEAF2` |
| `--color-ds-line` | `#CFCBDB` |
| `--color-ds-fg` | `#1F1B2A` |
| `--color-ds-fg2` | `#5A5468` |
| `--color-ds-fg-muted` | `#6B6579` |
| `--color-ds-accent` | `#6A55C2` |
| `--color-ds-accent-soft` | `rgba(106, 85, 194, 0.14)` |
| `--color-ds-btn` | `#6A55C2` |
| `--color-ds-success` | `#256B29` |
| `--color-ds-warning` | `#7A5708` |
| `--color-ds-danger` | `#B3362B` |
| `--color-ds-info` | `#1F6F9C` |
| `--color-ds-chart` | `#6A55C2` |
| `--color-ds-chart2` | `#7A5708` |
| `--color-ds-chart3` | `#5B46B5` |
| `--color-ds-grid` | `#DAD6E4` |

## Spacing

| Variable | Value |
|---|---|
| `--space-1` | `4px` |
| `--space-2` | `8px` |
| `--space-3` | `12px` |
| `--space-4` | `16px` |
| `--space-5` | `24px` |
| `--space-6` | `32px` |

## Radius

| Variable | Value |
|---|---|
| `--radius-sm` | `2px` |
| `--radius-md` | `2px` |

## Text size

| Variable | Value |
|---|---|
| `--font-size-xs` | `12px` |
| `--font-size-sm` | `13px` |
| `--font-size-md` | `14px` |
| `--font-size-lg` | `16px` |
| `--font-size-xl` | `20px` |
| `--font-size-tag` | `12px` |

## Fonts

| Variable | Value |
|---|---|
| `--font-ui` | JetBrains Mono (fallback: ui-monospace, "SF Mono", Menlo, Consolas, monospace) |
| `--font-mono` | JetBrains Mono (fallback: ui-monospace, "SF Mono", Menlo, Consolas, monospace) |

## Layout

| Variable | Value |
|---|---|
| `--layout-tab-header-height` | `36px` |
| `--layout-status-bar-height` | `24px` |
| `--layout-ribbon-width` | `48px` |
| `--layout-sidebar-width` | `224px` |
| `--layout-right-panel-width` | `400px` |
| `--layout-window-min-width` | `960px` |
| `--layout-window-min-height` | `600px` |
| `--layout-touch-target` | `44px` |
| `--layout-drawer-shadow` | `0 0 24px rgb(0 0 0 / 0.4)` |
| `--layout-control-h` | `28px` |

## Motion: durations

| Variable | Value |
|---|---|
| `--duration-fast` | `120ms` |
| `--duration-base` | `200ms` |
| `--duration-slow` | `320ms` |

## Motion: easing

| Variable | Value |
|---|---|
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` |

