# Security

## Reporting a problem

Please report a security problem privately, not in a public issue. Open a private advisory on the
project's GitHub page (Security, then "Report a vulnerability"). Say what you did, what happened, and
which version you used. You should get an answer within 7 days.

## What the app protects

- **Keys.** API keys are kept in the operating system's keychain, never in `config/settings.toml`. The
  backend log masks anything that looks like a key before a line is written.
- **The app from its agents.** An agent's file tools cannot read or edit the app's folder. With "Shell for
  every agent" on, the agent's program also runs in a sandbox (bubblewrap): the system and the app's folder
  are read-only, other agents' inboxes are read-only, private folders such as `~/.ssh` are empty, and the
  agent sees only its own processes.
- **Messages.** An agent can send only as itself: the sender is the folder a message was found in, not
  what the file says.
- **Notes.** Text from notes, files and other agents is treated as data, not as orders.

## Known limits

- The sandbox is off by default and has been tested with Claude Code only. Codex, Gemini and OpenCode
  agents keep their own rules.
- Inside the sandbox the home folder is still writable, because the command-line programs keep their
  own settings there. Folders outside the app, the hive and the private list are not protected.
- Without the sandbox, the main agent's shell is fenced by word patterns only. A pattern list cannot
  cover every command.
