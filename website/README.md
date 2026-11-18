# Website

The project's website: static pages, one stylesheet, and one small script (`account.js`) for the account and share-link pages. No build step, no cookies, nothing loaded from other sites (the fonts are in `fonts/`).

Open `index.html` in a browser to read it. `changelog.html` is made from `CHANGELOG.md`.

**Not deployed.** The plan says not to publish it until the security review is done (docs/SECURITY-REVIEW.md) and the owner says yes. `account.html` (14.03) and `share.html` (14.04) talk to the Supabase project in `core/account.py`. Before they work on the live site, add the site's address to Supabase > Authentication > URL Configuration > Redirect URLs.
