# Contributing to Hippocampus

Thanks for helping. Hippocampus is MIT-licensed, and contributions are accepted under the same license.

## Developer Certificate of Origin (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/) instead of a Contributor License Agreement. By signing off your commits, you certify that you wrote the change or have the right to submit it under the MIT license.

Sign off every commit with `-s`:

```
git commit -s -m "Describe your change"
```

This adds a line like `Signed-off-by: Your Name <you@example.com>` to the commit message. Pull requests with unsigned commits will be asked to amend.

## Before you open a pull request

- Keep changes small and focused on one thing.
- Include tests for new behavior.
- Don't include API keys, personal notes, or model weights in commits.
- Don't add code copied from projects with incompatible licenses (for example GPL code into this MIT codebase).
- Use the design tokens in `design/tokens.json` for colors and spacing. Don't hardcode new colors in components.

## Reporting bugs and security issues

Open an issue for bugs. For security problems, please don't post details publicly. Contact the maintainer privately first.
