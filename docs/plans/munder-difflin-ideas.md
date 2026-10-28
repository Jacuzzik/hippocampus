# Next plan: ideas from Munder Difflin 0.5.7

Source: the app map in Obsidian, `Research/Munder Difflin app map.md`. Ideas only; nothing is copied from Munder Difflin. Status: proposed, not started.

## Priority 1: safety and control (do first)
1. **Per-direction network switch.** Off / Listen / Converse / Open for anything that reaches outside the vault (AI calls, sync, webhooks). Default Off.
   - Done when: each direction can be set alone, and Off blocks all outbound calls in a test.
2. **Budget limits with a stop.** Token or cost cap per day, week and month, for the whole app and for each assistant. Over the cap, the assistant pauses and asks.
   - Done when: a test with a tiny cap pauses the next request and shows a card.
3. **Approval history.** Every write the assistant makes is logged with the card that approved it.
   - Done when: the activity log shows who approved each change.

## Priority 2: see what is happening
4. **Activity log view.** One list of handoffs, tool calls, approvals and errors, with filters.
5. **"Ask me" queue.** Questions the assistant cannot answer, shown in one place, with a respond button.
6. **Memory search by meaning.** Optional semantic search, shown as "Not set up" until its model is installed. Text search stays the default.

## Priority 3: keep it tidy
7. **Auto-trim long memory.** When a memory file passes a size limit, move the oldest notes to an archive file and leave an index.
8. **Scheduled notes jobs.** Repeating jobs (for example, weekly link check), with a count of how many are on.

## Priority 4: later
9. **Short-lived helper jobs.** A limit of 4 at once; each job runs once and reports back.
10. **Share a note by password link**, valid for 60 minutes by default.
11. **Skills panel.** List installed skills with open-folder and remove actions.
12. **Keys and secrets panel.** Saved keys take effect at once, with no restart; never shown in full.

## Checks before each step
- Run `.venv/bin/python -m pytest -q -p no:cacheprovider` and `cd app && npm test` (Node 24).
- Run `npm run check` for type errors.
- No push without the owner's yes.
