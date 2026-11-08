# Final tests: Hippocampus app

Each fix that needs testing goes here. Tick it off when it passes on screen.
Restart the app before testing: none of these have been seen on screen yet.

## Agent cards

- [ ] Main card: provider logo and name show (the old black square and missing name should be gone).
- [ ] Normal cards: provider logo and name show in the gap under the agent name.
- [ ] Normal cards: height is the same as before the provider change.
- [ ] Main card and normal cards: CMD shows the running command, or the last command when none runs.
- [ ] CTX bar: fills to the context % and shows the % text.
- [ ] Status: Working or Idle, matching the terminal.
- [ ] MODEL (main and normal cards): shows the live model for Claude agents. Codex and Ollama still show the saved setting.
- [ ] Highlight colours: CMD highlight and accent bar on the main card.

## Providers and terminals

- [ ] Terminal runs for: Claude, Codex, OpenAI (via Codex), Ollama, Antigravity (`agy`).
- [ ] Gemini CLI: needs `gemini` installed on this computer. Until then the terminal reports it is not installed.
- [ ] Not done: 11 API-only providers have no terminal (OpenAI API, xAI, Moonshot, Google Gemini API, Qwen, DeepSeek, Mistral, Groq, OpenRouter, LM Studio, vLLM). Decision pending: use OpenCode, or build a chat runner for each.
- [ ] Not done: every model needs a terminal. Same decision as above.
- [ ] Logos missing for xAI, Groq, Moonshot and Antigravity. Check which show a blank or square.
