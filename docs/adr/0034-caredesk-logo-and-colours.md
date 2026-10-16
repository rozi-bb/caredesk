# ADR-0034: CareDesk logo and colours

- Status: Accepted
- Date: 2026-10-16

## Context

The web chat showed Chainlit's logo, favicon, and colours, so users saw the framework instead of the product (roadmap "CareDesk look in the chat UI", step D1). CareDesk needs its own logo in a light and a dark version and a small icon for the browser tab.

## Decision

- **Icon**: a speech bubble (an assistant you talk to) with a leaf cut out of it (Evergreen Care Home). No medical cross or plus sign: CareDesk is administrative and declines clinical questions, so a medical symbol would promise the wrong thing, and the red cross emblem is legally protected. The owner chose this from three sketches (bubble and leaf, the letter C and a leaf, a house and a bubble). The house was hard to read at favicon size, and the C did not say what the product is.
- **Wordmark**: "CareDesk" in Inter SemiBold, converted to outlines, so it looks the same on every computer. A logo shown as an image cannot load web fonts. Inter is under the SIL Open Font License, which allows its use in logos.
- **Colours**, with their contrast ratios (WCAG AA needs at least 4.5:1):

  | Use | Colour | Background | Contrast |
  |---|---|---|---|
  | Light mode: icon and wordmark | `#1F6F5F` | white | 6.0:1 |
  | Dark mode: icon | `#6CC5B0` | Chainlit dark `#212121` | 7.9:1 |
  | Dark mode: wordmark | `#E8F5F1` | `#212121` | 14.4:1 |

  The leaf is white in light mode and `#212121` in dark mode, so it reads as a cut-out.
- **Files**, all SVG, in `src/ui/public/`: `logo_light.svg`, `logo_dark.svg`, and `favicon.svg`. The favicon switches its colours with the browser's dark mode. Chainlit 2.12 serves `public/logo_{light,dark}.*` and `public/favicon.*` in any format, so no PNG copies are needed.

## Buttons, links, and focus

`src/ui/public/theme.json` overrides three of Chainlit's colour variables, and leaves the backgrounds, sidebar, and body text as Chainlit draws them:

| Variable | Light | Dark | Contrast |
|---|---|---|---|
| `--primary` (buttons, links, active controls) | `#1F6F5F` | `#6CC5B0` | links 6.0:1 on white, 7.9:1 on `#212121` |
| `--primary-foreground` (text on buttons) | white | `#102A24` | 6.0:1 and 7.4:1 on the button |
| `--ring` (keyboard focus outline) | `#1F6F5F` | `#6CC5B0` | |

Dark mode uses the light green with dark text, not the dark green with white text: the dark green almost disappears against Chainlit's `#212121`, and white on a middle green reaches only 3.4:1. Chainlit opens in dark mode unless the user picks light, so most users see the light green first.

## Sign-in page

- The title is "Sign in to CareDesk" and the button says "Sign in", set in `src/ui/.chainlit/translations/en-US.json`. Chainlit 2.12's sign-in page has no subtitle, so the one-line description lives in the image instead.
- The large image is `src/ui/public/login.svg`: the CareDesk green with faint bubble and leaf shapes, and the logo in white with "Administrative assistant for Evergreen Care Home" in the middle. Chainlit crops it to fill half the screen, so everything that matters stays in the centre, and it is hidden below 1024 pixels wide. Chainlit gives the image the alt text "Image", so its words are decoration only; the page title carries the meaning.
- `login_page_image_dark_filter = "none"` in `config.toml`. Without a value, Chainlit darkens and greys the image in dark mode; "none" is not a Tailwind filter class, so no filter is applied.
- `custom_meta_url` and `custom_meta_image_url` point at the local app and `login.svg`. Left empty, Chainlit fills the page's link-preview tags (`og:url`, `og:image`) with its own GitHub page and banner.
- Chainlit writes its default translations into `.chainlit/translations/` and never overwrites a file that exists. That folder stays git-ignored except `en-US.json`, the only language the UI uses (`language = "en-US"`). A Chainlit upgrade that adds new texts will not add them to this file; compare it with the package's `en-US.json` after upgrading.

## How the files were made

The icon is drawn by hand in SVG on a 64-unit grid. The wordmark outlines were generated once with fontTools, run through `uv run --with fonttools` without adding it to the project: Inter's variable font set to weight 600 and optical size 32, then each letter of "CareDesk" drawn as a path with a cap height of 30 units. `login.svg` was made the same way, with its texts centred on a 1000 × 1200 canvas. Neither the font nor the generators are in the repository; to change the wordmark or the image text, repeat these steps.

## Alternatives considered

- **Plain text in the SVG with a font list**: no font download, but the letters change between Mac and Windows.
- **PNG files**: blurry when scaled, and a light and a dark copy at several sizes.
- **Teal or blue from a generic palette**: green ties the product to Evergreen Care Home.

## Consequences

- Browsers cache the old logo and favicon; a hard reload is needed to see the change.
- The chat page in Chainlit 2.12 has no logo in its header; the CareDesk icon appears there only as the assistant's avatar, which Chainlit takes from the favicon.
