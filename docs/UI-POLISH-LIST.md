# UI polish list

Made 2026-11-21 from screenshots of every right-panel tab, every Settings page, the dialogs and the nine
dashboards, at 1920x1080 and 1280x800 (Playwright with the mocked backend). One row per problem.
A row is done only when a check proves it: an e2e test, a baseline screenshot, or both.

| Id | Screen | Problem | Fix | State |
|---|---|---|---|---|
| U.01 | Dashboards | Opened as a full-window cover; the tiles sat in a small strip at the top with empty space under them; the calendar left a gap above its form | A dashboard now sits in the window's grid: notes, graph and Control Room hide (still mounted), the bottom bar goes, the agent cards stand in a column on the right. Tiles share the board in a near-square grid; the month grid stretches. A Graph entry goes back. | Done: `dashboards.spec.ts` layout test on all nine dashboards |
| U.02 | Note list | The tag dropdown grew to fill the column, pushing the tags and the note list to the middle of the sidebar | The dropdown keeps its own height in the sidebar | Done: baseline `main-dark`, `main-light` |
| U.03 | Control Room tabs | Eleven tabs in rows of four left an empty cell at the end of the last row | The last tab stretches over the empty cells | Done: baseline `tab-temps` |
| U.04 | Settings | The dialog was 920x640 on any screen: the page list scrolled and most pages scrolled | 1200x880 at most, 90% of a smaller window | Done: baseline `settings-appearance`, `matrix.spec.ts` |
| U.05 | Settings rows | Short values were squeezed to a narrow column and broke mid-word ("Only when you chat" on four lines, "recorde d"); "Check again" took two lines | A value keeps its width up to half the row; buttons in a row do not wrap | Done: screenshots; one case left, see U.06 |
| U.06 | Settings, Privacy and data | "0 recorded" next to the Clear button still takes two lines | Put the count and the button in one group that does not wrap | Open (minor) |
| U.07 | Control Room, triggers | Label, To, Name and Runs fields have different widths, so the form edges do not line up | One two-column form grid for missions and webhooks | Open (minor) |
| U.08 | Bottom bar | The main agent card nearly touches the bottom edge (136 px bar, 126 px card) | Even padding above and below the card | Open (minor) |
| U.09 | Dropdowns | Dropdowns use the cream card colour on the dark theme | Kept: it matches the pixel agent cards on purpose | Decided: no change |
