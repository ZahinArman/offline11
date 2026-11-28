# Product

<!-- impeccable:product-schema 1 -->

## Platform

web (this record covers the public releases site; the app itself is a Windows desktop tray app built with pywebview)

## Stack

Static HTML/CSS in `docs/`, served by GitHub Pages from the `main` branch. No build step, no framework.

## Users

People on Windows 10/11 who stay up later than they mean to and want their PC to turn off at a set time each night. On the releases site they want three things: see what ShutCap is, download the newest installer, and find out what changed.

## Product Purpose

ShutCap turns the PC off once each night at a time the user picks. It warns 45 and 25 minutes before, then counts down. At zero Windows gives apps 60 seconds to close and shuts down.

## Positioning

A nudge, never a lockout. It acts once per night, has an emergency cancel that writes a reason to a log, and never forces apps closed (`shutdown /s /t 60`, no `/f`). No account, no telemetry, no cloud.

## Capabilities and Constraints

- Free, MIT licence. Installer: `ShutCap-Setup.exe` on GitHub Releases. Not code-signed: SmartScreen shows a warning.
- Needs Microsoft Edge WebView2 (included in Windows 11). No admin rights.
- Named OFFLINE 11 before v2.0.0. Users of the old app must uninstall it first.
- Optional phone push via ntfy.sh (opt-in).

## Brand Commitments

- All user-facing text uses ASD-STE100 Simplified Technical English (short sentences, active voice, one instruction per sentence). The README already does.
- The app's design system (`shutcap/ui/web/base.css`) is the visual authority: Anthropic colour (ivory / charcoal, clay accent) and serif display type; follows light/dark.
- The launch film is the brand's main asset.

## Evidence on Hand

- Launch film, 44.5 s, 16:9: `docs/media/shutcap-launch-1080p.mp4` (source: `D:\Videos\ShutCap Launch Video`).
- Release history: v1.0.0, v1.1.0 (OFFLINE 11), v2.0.0, v2.1.0 (ShutCap) on GitHub Releases.
- No testimonials, user counts, or press. Do not invent them.

## Product Principles

1. Never overwhelm: what the reader must know first, details only on request.
2. Say only what the app really does; every claim maps to code or a test.
3. Calm, not strict. The product respects the user's choice.

## Accessibility & Inclusion

Readable at 200% zoom, keyboard reachable, captions-free film has its voiceover text available on the page, respects reduced motion.
