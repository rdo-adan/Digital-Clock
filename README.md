# Digital clock to control your time and study routine
## Clock Pro — Advanced Productivity Timer

A lightweight desktop productivity timer and clock built with Python + Tkinter.  
Combines a clock, multiple alarms, countdown timer, stopwatch and Pomodoro workflow with tagging and persistent statistics.

Reference implementation: [digital_clock.py](https://github.com/rdo-adan/Digital-Clock/blob/d84ede5fe32152f0ae2462cc808ff725484697dc/digital_clock.py)

---

## Table of contents

- [Features](#features)
- [Quickstart](#quickstart)
- [Dependencies](#dependencies)
- [Usage](#usage)
- [Pomodoro tags (markers)](#pomodoro-tags-markers)
- [Configuration and data](#configuration-and-data)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Behavior notes & limitations](#behavior-notes--limitations)
- [Development notes & suggested improvements](#development-notes--suggested-improvements)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- Desktop clock (12h / 24h) with selectable themes and window modes (mini / normal / full).
- Multiple alarms: add, enable/disable, remove (alarms auto-disable after firing).
- Countdown timer with configurable presets and custom minutes/seconds entry.
- Stopwatch (start / pause / reset).
- Pomodoro flow:
  - Default cycle: 25 min work → automatic 5 min break.
  - Tagging: label sessions with emoji/text tags (e.g. `💻 Code`).
  - Records history and updates aggregated statistics.
- Statistics view with totals and per-tag breakdown, plus CSV export.
- Native notifications (macOS `osascript`, Linux `notify-send`, Windows via `plyer` when available).
- Optional sounds generated/played with `pygame` + `numpy` or a custom sound file.
- Persistent configuration & history stored in a JSON file under the user's home directory.

---

## Quickstart

1. Clone the repository:
   ```bash
   git clone https://github.com/rdo-adan/Digital-Clock.git
   cd Digital-Clock
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   .\.venv\Scripts\activate    # Windows
   ```

3. (Optional) Install sound/notification dependencies:
   ```bash
   pip install numpy pygame plyer
   ```

4. Run the app:
   ```bash
   python3 digital_clock.py
   ```

---

## Dependencies

- Required:
  - Python 3.x
  - Tkinter (usually bundled with Python on most platforms)

- Optional (for better sound and Windows notifications):
  - numpy
  - pygame
  - plyer

If optional dependencies are missing, the app still runs, but sound playback and some notification features will be limited or disabled.

---

## Usage

- Top bar:
  - Choose theme and sound.
  - Toggle 24h / 12h format.
  - Switch window mode (mini / normal / full).
  - Open statistics window.

- Views:
  - Alarms: add an alarm (hour, minute, label). Alarms are listed in a scrollable pane, can be enabled/disabled, or removed.
  - Timer: use quick presets or custom minute/second input. Start / pause / stop controls available.
  - Stopwatch: standard start / pause / reset.
  - Pomodoro: pick a tag (categorize work), start a 25-minute session. After work completes, session is recorded and a 5-minute break starts automatically.

- Notifications and sound:
  - When an alarm, timer, or pomodoro phase finishes, the app shows a notification and a message dialog, and attempts to play the selected sound.
  - If you pick "Custom" sound, you will be prompted to select an audio file.

---

## Pomodoro tags (markers)

Default tag list used by the app (editable in code or future UI enhancements):

- 🧬 Bio
- 📊 Data
- 📖 Reading
- ✍️ Writing
- 💻 Code
- 🎓 Study

How to use:
1. Open the Pomodoro view.
2. Select a tag from the dropdown (or leave blank).
3. Start the Pomodoro session. When completed, the session is recorded under that tag.

To change the default tags now, edit the `tags` list inside `digital_clock.py`:
```python
tags = ["🧬 Bio", "📊 Data", "📖 Reading", "✍️ Writing", "💻 Code", "🎓 Study"]
```
(Located near the Pomodoro UI setup — see the referenced file above.)

---

## Configuration and data

- Configuration + data file location (per user):
  - `~/.clockpro/clock_config.json`
- Stored data includes:
  - theme, sound, time format, time offset
  - alarms list
  - pomodoro_history (date, tag, timestamp)
  - stats (total pomodoros, total minutes, sessions_by_tag)
  - window mode and timer presets

Export:
- Use the "Statistics" window → "Export CSV" to save pomodoro history as CSV.

---

## Keyboard shortcuts

- Space: Start / pause timer, pomodoro, or stopwatch depending on the active view.
- r / R: Reset stopwatch.
- Esc: Hide current view.
- 1 / 2 / 3 / 4: Switch to alarm / timer / stopwatch / pomodoro views.
- p / P: Play the configured sound.

---

## Behavior notes & limitations

- Alarm matching uses exact string compare on `HH:MM:SS`. If the app misses the exact second (e.g., system sleep, blocked UI, or the app was not running at that exact second), the alarm can be missed. Consider this when relying on precise alarms.
- Sound volume fade logic is incomplete: the code contains a placeholder for progressive fade but does not schedule the fade steps. If you need a smooth fade-in/out, this must be implemented (use `threading` or `Tk.after`).
- Alarms are automatically disabled after firing. There is no built-in recurring/repeat option currently.
- UI is built with Tkinter — functional and cross-platform, but visually simple compared with modern GUI frameworks.
- If `pygame` or `numpy` are not installed, generated tones will not be available; custom sound files may still be used if `pygame` is installed.

---

## Development notes & suggested improvements

Possible improvements worth opening issues / PRs for:

- Implement tolerant alarm checking (e.g., check alarms between previous tick and now to avoid missing when exact second is missed).
- Complete the sound fade logic using `root.after(...)` or a background thread.
- Provide a UI to manage Pomodoro tags persistently (add/edit/remove tags saved to config).
- Add configurable Pomodoro durations (work / short break / long break) in settings.
- Add recurring alarms and more advanced scheduling (daily/weekday/monthly).
- Add unit tests for TimerLogic, StopwatchLogic and PomodoroLogic.
- Improve error handling and log messages for failed sound playback and notifications.

---

## Contributing

1. Fork the repository.
2. Create a branch for your change: `git checkout -b my-feature`
3. Make changes + tests.
4. Open a pull request describing the change and why it helps.

When reporting bugs, include:
- Operating system and Python version
- Whether optional dependencies (`pygame`, `numpy`, `plyer`) are installed
- Console output and any stack traces

---


---


