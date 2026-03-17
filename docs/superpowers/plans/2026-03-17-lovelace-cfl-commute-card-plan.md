# CFL Commute Lovelace Card Implementation Plan

**Goal:** Create a Lovelace card for displaying CFL train commute information

**Based on:** UK my-rail-commute-card (https://github.com/adamf83/lovelace-my-rail-commute-card)

---

## File Structure

```
lovelace-cfl-commute-card/
├── src/
│   ├── cfl-commute-card.js     # Main card component
│   ├── styles.js               # CSS styles
│   ├── editor.js               # Visual editor
│   └── utils.js               # Helper functions
├── dist/                      # Built files
├── examples/                  # Example configurations
├── tests/                     # Tests
├── package.json
├── rollup.config.js
├── hacs.json
└── README.md
```

---

## Chunk 1: Project Setup

### Task 1: Initialize Project

**Files:**
- Clone from UK card structure
- Create: `package.json`, `rollup.config.js`, `hacs.json`, `.babelrc`

**Steps:**
1. Fork/clone UK card structure
2. Replace "my-rail-commute" → "cfl-commute"
3. Update dependencies

---

## Chunk 2: Core Card

### Task 2: Main Card Component

**Files:**
- Modify: `src/cfl-commute-card.js`

**Changes from UK:**
- Entity type: `sensor.cfl_commute_*` instead of `sensor.my_rail_commute_*`
- Remove calling points (not in CFL API)
- Remove delay reasons (not in CFL API)
- Update status labels for Luxembourg

### Task 3: Styles

**Files:**
- Modify: `src/styles.js`
- Theme support: auto, light, dark

---

## Chunk 3: Views

### Task 4: Implement All View Modes

**View modes to implement:**
1. **Full View** - All details (time, platform, operator, category, direction)
2. **Compact View** - Mobile-friendly
3. **Next-Only View** - Single train focus
4. **Board View** - Classic station board aesthetic

---

## Chunk 4: Features

### Task 5: Configure Options

**Config options:**
- `entity` - Required sensor entity
- `title` - Card title
- `view` - full/compact/next-only/board
- `theme` - auto/light/dark
- `show_header`, `show_route`
- `show_platform`, `show_operator`, `show_category`
- `hide_on_time_trains`
- `min_delay_to_show`
- `font_size` - small/medium/large
- `colors` - Custom colors
- `tap_action`, `hold_action`

### Task 6: Visual Editor

**Files:**
- Modify: `src/editor.js`

---

## Chunk 5: Build & Test

### Task 7: Build

```bash
npm install
npm run build
```

### Task 8: Test in Home Assistant

1. Copy dist to `/config/www/`
2. Add resource
3. Test all views
4. Test theme switching

---

## Summary

| Chunk | Tasks |
|-------|-------|
| 1 | Project setup |
| 2 | Core card |
| 3 | 4 view modes |
| 4 | All config options |
| 5 | Build & test |
