# CareDesk look in the chat UI

| | |
|---|---|
| Scope | Roadmap "CareDesk look in the chat UI" (D1–D5), [ADR-0034](../adr/0034-caredesk-logo-and-colours.md) |
| Date | 2026-10-16 |
| Result | Done |

## Why

The web chat showed Chainlit's logo, favicon, pink buttons, and sign-in text, so users saw the framework instead of the product.

## Build

| Step | What |
|---|---|
| D1 | Three icon sketches; the owner chose the speech bubble with a leaf. Icon drawn by hand in SVG; "CareDesk" in Inter SemiBold turned into outlines with fontTools (run once with `uv run --with fonttools`, not a project dependency). `logo_light.svg`, `logo_dark.svg`, and `favicon.svg` (switches colours with the browser's dark mode) in `src/ui/public/` |
| D2 | No config needed: Chainlit 2.12 serves `public/logo_{light,dark}.*` and `public/favicon.*` in any format. The chat page has no header logo in this version; the assistant's avatar comes from the favicon |
| D3 | Title "Sign in to CareDesk" and button "Sign in" in `translations/en-US.json`. `login.svg` (green, faint shapes, white logo and tagline) as `login_page_image`, with `login_page_image_dark_filter = "none"` so Chainlit does not darken it. A sketch was shown and approved first |
| D4 | `src/ui/public/theme.json` overrides `--primary`, `--primary-foreground`, and `--ring`: dark green with white in light mode, light green with dark text in dark mode |
| D5 | `custom_meta_url` and `custom_meta_image_url` set, so the link-preview tags no longer point at Chainlit |

## Test

| Check | How | Result |
|---|---|---|
| Contrast | WCAG ratios computed for every colour pair: 6.0:1 to 14.4:1, all above 4.5:1 | Pass |
| Sign-in page | Browser, 1280 px wide, dark and light; 375 px wide | Pass: logo, title, green button and image; image hidden on a phone |
| Chat page | Signed in as a demo staff account; dark and light; 375 px wide with the sidebar open | Pass: send button, account circle, and avatar in CareDesk green |
| Other pages | Readme, search window, account menu, an earlier conversation | Pass: no pink, no Chainlit |
| Leftover branding | Searched the page's visible text, alt text, labels, and `<head>` for "Chainlit" | Pass after D5; before it, `og:image` and `og:url` named Chainlit |
| UI unit tests | `uv run pytest tests/unit_tests/test_ui.py` | Pass, 15 tests |
| Links inside answers | Not seen directly: no message was sent to the agent. They use `--primary`, which was checked | Not verified by eye |

## Findings

- The pattern next to the sign-in form was Chainlit's favicon, enlarged and darkened. Replacing the favicon changed it too, which is why D3 needed an image of its own.
- Chainlit 2.12's sign-in page has no subtitle; the one-line description went into the image.
- `.chainlit/translations/` was git-ignored as generated files, so the new title would have been lost on a fresh clone. Chainlit never overwrites an existing translation file, so `en-US.json` is now tracked and the rest stays ignored. After a Chainlit upgrade, compare it with the package's copy for new texts.
- Chainlit opens in dark mode by default, so most users see the light-green version first.
- Browsers keep the old logo and icon until a hard reload.
