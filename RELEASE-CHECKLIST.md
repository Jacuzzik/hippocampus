# Release checklist

Work down the list. A box is ticked only when the step was run and passed.

## Before the build

- [ ] The branch is up to date with `main` and CI is green on it.
- [ ] `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -q` pass.
- [ ] In `app/`: `npm run format:check`, `npm run lint`, `npm run check`, `npm test` pass on Node 24.
- [ ] In `app/`: `npx playwright test --workers=1` passes.
- [ ] The version is the same in `pyproject.toml`, `app/package.json` and `app/src-tauri/tauri.conf.json`.
- [ ] `CHANGELOG.md` has an entry for this version.

## Screens

- [ ] Start the app and take a screenshot of: the graph, the Control Room (each tab), an agent's panel,
      Settings (each page), the Control panel. No overlap, no clipped text, no error bar.
- [ ] An agent's terminal draws cleanly after a window resize and after a backend restart.

## Install test

- [ ] Build the installer and install it on a machine that has never had the app.
- [ ] First run: pick a vault, add an agent, send it a message from the Inbox tab, and see the reply.
- [ ] Turn "Shell for every agent" on, restart an agent, and check it still starts and can read notes.

## Publish

- [ ] Tag the commit `vX.Y.Z` and push the tag.
- [ ] Attach the installers and their checksums to the GitHub release.
- [ ] Merge to `main` only with the owner's yes. Never force-push.
