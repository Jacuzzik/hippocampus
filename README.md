# Hippocampus

Hippocampus is an open-source desktop "second brain." Your notes live as Markdown files in a local folder, called a brain. You get an Obsidian-style graph of how they link, an AI assistant that can read and write notes (with your confirmation), and an orb that shows what the assistant is doing.

It is local first: your notes stay on your machine. The only network calls go to the model provider you configure.

Linux comes first, then Windows, then macOS.

## Status

Early development, phase D2: a static desktop shell with four regions, and a vault index that the UI doesn't use yet. See [AGENTS.md](AGENTS.md) for the architecture and roadmap.

## Run

Tested on Arch Linux under Wayland. You need Rust, [uv](https://docs.astral.sh/uv/), and Node 24 or newer.

Install the system packages Tauri needs:

```bash
sudo pacman -S --needed webkit2gtk-4.1 base-devel curl wget file openssl \
  appmenu-gtk-module libappindicator-gtk3 librsvg
```

Set up the Python sidecar and run its tests:

```bash
uv sync --locked
uv run pytest
```

Start the app:

```bash
cd app
npm ci
npm run tauri dev
```

The first run compiles the Rust shell, which takes a few minutes.

### Index a vault

The sidecar can index a folder of Markdown notes, including `[[links]]`, `#tags` and frontmatter `tags:`, into a SQLite file under `storage/index/`. The index is only a cache, so you can delete it at any time and it gets rebuilt.

Make a sample vault of 200 generated notes and index it:

```bash
uv run python tests/fixtures/make_sample_vault.py brains/sample
uv run python -m core index brains/sample
```

Keep the index current while you edit notes. Stop with Ctrl+C:

```bash
uv run python -m core watch brains/sample
```

Both commands take `--storage DIR` to keep the index somewhere other than `storage/`. To include the 2,000-note timing check, run `uv run pytest -m slow`.

### Troubleshooting: blank window on Wayland

On some Intel GPUs, WebKitGTK's DMA-BUF renderer shows a blank or white window. If that happens, start the app with the renderer turned off:

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 npm run tauri dev
```

The app does not set this for you.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Every commit must be signed off (`git commit -s`) under the Developer Certificate of Origin.

## License

MIT. See [LICENSE](LICENSE). The name and logo are covered by [TRADEMARKS.md](TRADEMARKS.md).
