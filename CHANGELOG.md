# Changelog

## Unreleased

### Added
- One inbox for agents: messages carry a type, a task id, a reply link and a priority. The Inbox tab
  groups them into conversations, filters, searches, and has a box to write to one agent or all.
- "Shell for every agent" (Settings > Agents, off by default): each agent gets a fenced shell and its
  program runs in a sandbox that keeps the app and the system read-only.
- Agent panel: Traces lists every tool call with its result; Messages lists that agent's messages.
- Settings > Advanced: feature switches and the backend log.
- TALK on a card opens that agent's message box.
- Planned cards say what a feature will do and what is missing, in place of "Not set up".

### Changed
- One terminal component for the main agent and added agents.
- The graph reads the vault only after a file changed, not every five seconds.
- Control Room panels refresh while open.
- Each agent's briefing ends with the limits in force and a version stamp; a broken briefing stops the
  agent before it starts.

### Fixed
- The agents' programs start again by themselves after the backend restarts.
- The start-up inbox was typed into every agent again on each window reload.
- Two lines typed at once could mix in one input, so `/remote-control` was sent to the model as chat.
- Sending a task from the app never worked (`task_send` was registered without its arguments).
- Garbled agent terminal after a resize.

### Removed
- The unused in-app chat pane, and the tests for a phone and tablet layout that does not exist.
