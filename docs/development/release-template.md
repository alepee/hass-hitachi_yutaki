# Release template

Follow this template when cutting a release so titles and descriptions stay consistent with past releases (derived from the `v2.1.x` release notes). It covers three artifacts: the **version-bump commit/PR**, the **GitHub Release title**, and the **GitHub Release body**.

## Release flow (recap)

`make bump [PART=minor|major]` on `main` → commit → push → create the GitHub release with the tag. See [AGENT.md](../../AGENT.md#release-process). `make bump` updates `manifest.json` (source of truth) and `pyproject.toml`, and moves the `[Unreleased]` CHANGELOG entries under the new version.

## Bump commit / PR title

Use a `release:` prefix with the bare version:

```
release: X.Y.Z
```

## GitHub Release title

The release **name/tag** is `vX.Y.Z`. The release **body** opens with a themed H1 summarizing the release in a few words:

```
# Hitachi Yutaki vX.Y.Z — <short theme>
```

Examples: `— Gateway recovery logging`, `— Pre-2016 Gateway Support, Anonymous Telemetry & Electricity Costs`.

## GitHub Release body

Scale the sections to the release size (a patch may only need intro + Installation + Changelog; a minor/major uses Highlights + per-feature sections). Keep the emoji section headers used in past releases.

```markdown
# Hitachi Yutaki vX.Y.Z — <short theme>

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/vX.Y.Z/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/vX.Y.Z)

<One or two sentences: what this release delivers and why it matters. Link the driving issues, e.g. ([#356](https://github.com/alepee/hass-hitachi_yutaki/issues/356)).>

## 🎯 Highlights   <!-- minor/major only -->

- **<Feature>** — one-line value statement
- **<Feature>** — one-line value statement

## ✨ What's New   <!-- or "New Features" -->

### <Feature title> ([#NNN](https://github.com/alepee/hass-hitachi_yutaki/issues/NNN))

<What changed, from the user's point of view. Include a short log/config snippet when it helps.>

## 🐛 Bug Fixes   <!-- if any -->

### <Fix title> ([#NNN](https://github.com/alepee/hass-hitachi_yutaki/issues/NNN))

<What was wrong and what the user will now observe.>

## 📦 Installation

1. Update to `vX.Y.Z` via HACS
2. Restart Home Assistant

<State migration needs explicitly: "No configuration changes or migration needed." or the required steps.>

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type (ATW-MBS-02 Line-up 2016 / Before 2016, or HC-A(16/64)MB)
- Relevant logs (`custom_components.hitachi_yutaki`)

---

**Full Changelog:** [vPREV...vX.Y.Z](https://github.com/alepee/hass-hitachi_yutaki/compare/vPREV...vX.Y.Z)
```

## Notes

- Write release notes from the **user's** perspective (observable behavior), not the implementation diff. The `CHANGELOG.md` entries are the raw material; the release body reframes them.
- Reuse the exact section headers and emoji above so releases read consistently.
- Always end with the `Full Changelog` compare link against the previous tag.
