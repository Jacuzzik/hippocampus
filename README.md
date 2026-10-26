# Hippocampus

Hippocampus is an open-source desktop "second brain." Your notes live as Markdown files in a local folder, called a brain. You get an Obsidian-style graph of how they link, an AI assistant that can read and write notes (with your confirmation), and an orb that shows what the assistant is doing.

It is local first: your notes stay on your machine. The only network calls go to the model provider you configure.

Linux comes first, then Windows, then macOS.

## Status

Early development, phase D8: the desktop app has the brain graph, search, the assistant (chat, tool log, confirm cards, kill switch) and the orb, with Playwright tests for the critical paths. Packaged builds are not done: see the shortcuts in `app/src-tauri/src/sidecar.rs`. See [AGENTS.md](AGENTS.md) for the architecture and roadmap.

## Run

Every platform needs Rust, [uv](https://docs.astral.sh/uv/) and Node 24 or newer. The app is developed on Arch Linux under Wayland. CI runs the Python tests and the app checks on Ubuntu, macOS and Windows; the per-OS steps below say what each one needs.

### Linux

Arch Linux:

```bash
sudo pacman -S --needed webkit2gtk-4.1 base-devel curl wget file openssl \
  appmenu-gtk-module libappindicator-gtk3 librsvg
```

Debian or Ubuntu (the same packages CI installs, plus the build tools Tauri needs):

```bash
sudo apt update
sudo apt install build-essential curl wget file libxdo-dev libssl-dev \
  libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev
```

For other distributions, follow the [Tauri prerequisites for Linux](https://v2.tauri.app/start/prerequisites/#linux).

The assistant's key is stored in the Secret Service (GNOME Keyring or KWallet). Start one before you run `key set`. Without it the key cannot be saved and the assistant uses Ollama.

### macOS

Install the Xcode Command Line Tools. The full Xcode app is not needed for the desktop build:

```bash
xcode-select --install
```

Your key goes to the macOS Keychain, which needs no setup.

### Windows

- Install the [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) with the "Desktop development with C++" workload.
- Install Microsoft Edge WebView2. Windows 10 (version 1803 or later) and Windows 11 usually have it. If not, get the Evergreen Bootstrapper from Microsoft.
- Install Rust with [rustup](https://rustup.rs/), using the default MSVC toolchain.
- If you build an MSI installer, turn on the VBSCRIPT optional feature.

Your key goes to the Windows Credential Manager, which needs no setup. The commands below work in PowerShell too.

### Set up the Python sidecar

This creates the `.venv` that the app starts, and runs its tests:

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

The first run compiles the Rust shell, which takes a few minutes. The app opens the vault named in `config/settings.toml` (`brains/sample` by default), so create it first with the sample commands below.

### The assistant

The assistant uses Claude when a key is saved, and Ollama otherwise or when Claude fails.

- Save a Claude API key: `uv run python -m core key set` (it prompts; the key goes to the OS keychain, never to a file). `key status` and `key clear` do the rest.
- Ollama: install it, then `ollama pull qwen2.5:1.5b` (the default in `config/settings.toml`).
- Reads (search, read a note) run at once. Creating a note waits for your approval on a card that shows the exact change. Stop (or Escape) halts pending work within a second.

### Browser tests

The Playwright tests run the UI in Chromium with the Tauri bridge mocked, so they need no Rust build and no Python sidecar:

```bash
cd app
npx playwright install chromium   # once
npm run e2e
```

### Checks

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
cd app && npm run format:check && npm run lint && npm run check && npm test && npm run build
```

`npm test` uses Node's test runner on `.ts` files, so it needs Node 24 or newer (Node 24 strips the types on import).

### Index a vault

The sidecar can index a folder of Markdown notes, including `[[links]]`, `#tags` and frontmatter `tags:`, into a SQLite file under `storage/index/`. The index is only a cache, so you can delete it at any time and it gets rebuilt. It needs SQLite 3.35.0 or newer. The Python 3.12 that uv installs already includes a newer one, and CI also runs the tests against 3.35.0.

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

### Troubleshooting: blank window on Linux under Wayland

On some Intel GPUs, WebKitGTK's DMA-BUF renderer shows a blank or white window. If that happens, start the app with the renderer turned off:

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 npm run tauri dev
```

In PowerShell on Windows, this is not needed, and `$env:WEBKIT_DISABLE_DMABUF_RENDERER` has no effect there. The app does not set this for you.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Every commit must be signed off (`git commit -s`) under the Developer Certificate of Origin.

## License

MIT. See [LICENSE](LICENSE). The name and logo are covered by [TRADEMARKS.md](TRADEMARKS.md).
