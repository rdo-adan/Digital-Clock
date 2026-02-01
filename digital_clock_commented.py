# filepath: /Users/adan98/Documents/Digital Clock/Python/digital_clock_commented.py
#!/usr/bin/env python3
# Clock Pro - Advanced Productivity Timer (commented)
# This file is a commented educational version of digital_clock.py.
# It explains concepts and structures useful for a programming student:
# - module imports and why they are used
# - classes and encapsulation of responsibilities
# - GUI event loop basics with tkinter
# - separation of concerns (config, sound, logic, UI)
# - basic file IO (JSON config), scheduling with after, and state management
#
# Note: The functional code is preserved with inline comments explaining
# what each major block does. Comments are concentrated on classes, methods,
# and non-obvious logic paths so the student can learn without being overwhelmed.

"""
Clock Pro - Advanced Productivity Timer
Features: Multiple alarms, Pomodoro tracking, Statistics, System tray, Notifications

This module implements:
- A Tkinter GUI with multiple views (alarm, timer, stopwatch, pomodoro)
- Persistent configuration stored as JSON in the user's home directory
- Simple sound generation/playback when pygame is available
- Pomodoro workflow with tagging and statistics
- Basic notifications using platform-specific helpers

High-level architecture:
- ConfigManager: handles persistent settings (load/save/get/set)
- NotificationManager: platform-specific notification wrapper
- TimerLogic / StopwatchLogic / PomodoroLogic: contain the non-GUI logic
- SoundManager: encapsulates audio playback (uses pygame if available)
- StatsManager: records and exports productivity data
- ClockPro: the main GUI class that wires everything together
"""

# --------------------------
# Imports and environment
# --------------------------
# Standard library imports:
import tkinter as tk                            # tkinter: built-in GUI toolkit
from tkinter import ttk, messagebox, filedialog # ttk: themed widgets; messagebox/file dialogs
from time import strftime                       # strftime: format current time strings
from datetime import datetime, timedelta        # datetime/timedelta: date and time operations
import os                                       # os: operating system helpers (notifications, paths)
import sys                                      # sys: runtime platform detection
import json                                     # json: read/write configuration in JSON format
from pathlib import Path                        # pathlib.Path: convenient path manipulations

# Optional third-party libraries:
# pygame: used to generate and play tones if available (non-blocking)
# numpy: used to create waveforms for tones (if available)
try:
    import pygame
    import numpy as np
    # Initialize the audio mixer with a common sample rate and buffer size.
    # This may fail depending on the environment, so the import is wrapped.
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    SOUND_AVAILABLE = True
except:
    # If pygame or numpy are missing, sound features will be disabled gracefully.
    SOUND_AVAILABLE = False

# ===================== CONFIG MANAGER =====================
# The ConfigManager encapsulates all configuration persistence:
# - It stores a JSON config file under ~/.clockpro by default
# - Provides simple get/set and automatic save behavior
class ConfigManager:
    """Manages persistent configuration stored on disk using JSON.

    Responsibilities:
    - Provide defaults for missing values
    - Read/write the configuration file safely
    - Expose get/set helpers to the rest of the app
    """
    def __init__(self, config_file="clock_config.json"):
        # Build path: ~/.clockpro/clock_config.json
        self.config_file = Path.home() / ".clockpro" / config_file
        # Ensure parent directory exists
        self.config_file.parent.mkdir(exist_ok=True)
        # Load existing data or defaults
        self.data = self.load()
    
    def load(self):
        """Load configuration from disk and merge with defaults.

        Returning a dictionary so the app can use a single object for config.
        """
        default = {
            "theme": "Matrix",
            "sound": "Beep",
            "time_format_24h": True,
            "time_offset": 0,
            "alarms": [],
            "pomodoro_history": [],
            "stats": {
                "total_pomodoros": 0,
                "total_minutes": 0,
                "sessions_by_tag": {}
            },
            "window_mode": "normal",  # mini, normal, full
            "timer_presets": [1, 5, 10, 15, 25, 45]
        }
        
        # If a saved config exists, attempt to load and merge it with defaults.
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    default.update(loaded)  # merge user settings on top of defaults
            except:
                # On parse errors or IO errors, keep defaults to avoid crashes.
                pass
        
        return default
    
    def save(self):
        """Write current configuration back to disk.

        Using json.dump with indent for human-readable files.
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            # Print to stderr or console if saving fails; a real app might show UI feedback.
            print(f"Save config error: {e}")
    
    def get(self, key, default=None):
        """Helper to read a configuration value with an optional default."""
        return self.data.get(key, default)
    
    def set(self, key, value):
        """Helper to set a configuration value and persist immediately."""
        self.data[key] = value
        self.save()

# ===================== NOTIFICATION MANAGER =====================
# This manager shows simple native notifications depending on platform.
class NotificationManager:
    """Wraps native OS notifications.

    It uses:
    - osascript on macOS
    - notify-send on Linux
    - plyer notification on Windows (if available)
    The method is intentionally simple and tolerant of failures.
    """
    @staticmethod
    def show(title, message):
        """Show a native notification with a title and message.

        The implementation chooses an appropriate mechanism by checking sys.platform.
        """
        try:
            # macOS uses AppleScript via osascript for notifications.
            if sys.platform == 'darwin':
                os.system(f'''
                    osascript -e 'display notification "{message}" with title "{title}" sound name "Ping"'
                ''')
            # Linux: uses notify-send (common in desktop environments).
            elif sys.platform == 'linux':
                os.system(f'notify-send "{title}" "{message}"')
            # Windows: try to use plyer.notification if available as a fallback.
            elif sys.platform == 'win32':
                try:
                    from plyer import notification
                    notification.notify(title=title, message=message, timeout=10)
                except:
                    pass
        except Exception as e:
            # Notification errors are non-fatal; print for debugging.
            print(f"Notification error: {e}")

# ===================== CORE LOGIC =====================
# The core timer/stopwatch/pomodoro logic is separated from the UI so it is testable
# and easier to reason about. Each logic object exposes start/pause/stop/tick methods.
class TimerLogic:
    """Simple countdown timer logic.

    Design notes:
    - The timer stores 'remaining' seconds and a running/paused state.
    - A 'tick' method is intended to be called every second by the GUI loop.
    - Callbacks:
      - on_update(seconds) called whenever remaining changes
      - on_finish() called when timer reaches zero
    """
    def __init__(self, on_update=None, on_finish=None):
        self.running = False
        self.paused = False
        self.remaining = 0
        self.on_update = on_update
        self.on_finish = on_finish
    
    def start(self, seconds):
        """Start the timer with a given duration in seconds."""
        self.remaining = seconds
        self.running = True
        self.paused = False
    
    def pause(self):
        """Toggle pause state (pause/resume)."""
        self.paused = not self.paused
    
    def stop(self):
        """Stop and reset the timer."""
        self.running = False
        self.paused = False
        self.remaining = 0
    
    def tick(self):
        """Advance the timer by one second.

        Returns True if the timer is still running afterward.
        """
        if self.running and not self.paused and self.remaining > 0:
            self.remaining -= 1
            if self.on_update:
                # Update callback so UI can refresh display.
                self.on_update(self.remaining)
            if self.remaining == 0:
                self.running = False
                if self.on_finish:
                    # Notify that the timer finished.
                    self.on_finish()
        return self.running

class StopwatchLogic:
    """Stopwatch logic that counts elapsed seconds.

    The stopwatch supports start/pause/reset/tick. Similar pattern to TimerLogic.
    """
    def __init__(self, on_update=None):
        self.running = False
        self.paused = False
        self.elapsed = 0
        self.on_update = on_update
    
    def start(self):
        """Start counting from current elapsed value."""
        self.running = True
        self.paused = False
    
    def pause(self):
        """Toggle pause/resume for the stopwatch."""
        self.paused = not self.paused
    
    def reset(self):
        """Stop and reset elapsed time to zero; inform UI via callback."""
        self.running = False
        self.paused = False
        self.elapsed = 0
        if self.on_update:
            self.on_update(0)
    
    def tick(self):
        """Advance elapsed time by one second when running and not paused."""
        if self.running and not self.paused:
            self.elapsed += 1
            if self.on_update:
                self.on_update(self.elapsed)
        return self.running

class PomodoroLogic:
    """Pomodoro timer logic with simple work/break phases and tagging support.

    This class implements a typical 25-minute work / 5-minute break cycle.
    - start(tag=None): begins a work phase and stores an optional tag
    - on_update(time, phase): called each tick with remaining seconds and current phase
    - on_phase_complete(phase, count, tag): called when a phase completes
    """
    def __init__(self, on_update=None, on_phase_complete=None):
        self.running = False
        self.paused = False
        self.time = 0
        self.phase = "work"
        self.count = 0
        self.current_tag = None
        self.on_update = on_update
        self.on_phase_complete = on_phase_complete
    
    def start(self, tag=None):
        """Begin a pomodoro work period with optional tag."""
        self.running = True
        self.paused = False
        self.phase = "work"
        self.time = 25 * 60   # 25 minutes converted to seconds
        self.current_tag = tag
    
    def pause(self):
        """Toggle pause/resume for pomodoro timer."""
        self.paused = not self.paused
    
    def skip(self):
        """Skip the rest of the current phase by setting time to zero."""
        self.time = 0
    
    def tick(self):
        """Advance one second. Handle phase transitions when time reaches zero."""
        if self.running and not self.paused:
            if self.time > 0:
                self.time -= 1
                if self.on_update:
                    # Notify UI of updated remaining time and current phase
                    self.on_update(self.time, self.phase)
            else:
                # Transition logic when phase ends:
                if self.phase == "work":
                    # After work, enter short break and increment completed count
                    self.phase = "break"
                    self.time = 5 * 60  # 5 minute break
                    self.count += 1
                    if self.on_phase_complete:
                        self.on_phase_complete("work", self.count, self.current_tag)
                else:
                    # Break completed; stop the pomodoro run
                    self.running = False
                    if self.on_phase_complete:
                        self.on_phase_complete("break", self.count, self.current_tag)
        return self.running

# ===================== SOUND MANAGER =====================
# SoundManager centralizes audio generation and playback.
# It generates simple tones via numpy and pygame.sndarray if both are available.
class SoundManager:
    """Manages sounds and playback.

    Important design points:
    - If SOUND_AVAILABLE is False, the manager becomes a no-op (safe fallback)
    - Tones are generated programmatically to avoid shipping audio assets
    - The manager supports playing a sound in a loop and progressive volume fade
    """
    def __init__(self):
        self.sounds = {}
        self.current_playing = None
        self.custom_sound = None
        self.volume_job = None
        
        if SOUND_AVAILABLE:
            # Generate a few named tones for simple alerts
            self._generate_sounds()
    
    def _generate_sounds(self):
        """Create a dictionary of named pygame sounds by generating waveforms."""
        try:
            self.sounds["Beep"] = self._create_tone(440, 0.15)
            self.sounds["Alert"] = self._create_tone(1200, 0.2)
            self.sounds["Chime"] = self._create_tone(880, 0.25)
            self.sounds["Bell"] = self._create_tone(1760, 0.2)
            self.sounds["Alarm"] = self._create_tone(600, 0.35)
        except Exception as e:
            # If generation fails, log and continue without crashing
            print(f"Sound generation error: {e}")
    
    def _create_tone(self, freq, duration):
        """Generate a simple sine wave sound of a given frequency and duration.

        Returns a pygame Sound object or None if creation fails.
        """
        try:
            sr = 44100  # sample rate in Hz
            n = int(duration * sr)  # total number of samples
            # Create a time array evenly spaced over the duration
            t = np.linspace(0, duration, n, False)
            # Sine wave at frequency freq
            wave = np.sin(freq * t * 2 * np.pi)
            
            # Apply a short linear fade in/out to avoid clicks
            fade = int(sr * 0.01)
            wave[:fade] *= np.linspace(0, 1, fade)
            wave[-fade:] *= np.linspace(1, 0, fade)
            
            # Convert to 16-bit PCM range and duplicate channels for stereo
            audio = (wave * 32767).astype(np.int16)
            stereo = np.repeat(audio.reshape(n, 1), 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        except:
            # On failure, return None so callers can degrade gracefully
            return None
    
    def play(self, sound_name, loop=False, progressive=False):
        """Play a named sound or a custom audio file.

        Parameters:
        - sound_name: key for generated sounds or "Custom" to play a user-selected file
        - loop: whether to loop playback indefinitely (useful for alarm until dismissed)
        - progressive: whether to start at low volume and ramp up gradually
        """
        if not SOUND_AVAILABLE:
            # No sound subsystem available; do nothing
            return
        
        try:
            if sound_name == "Custom" and self.custom_sound:
                # Play an arbitrary audio file using the music player API
                pygame.mixer.music.load(self.custom_sound)
                pygame.mixer.music.set_volume(0.3 if progressive else 1.0)
                pygame.mixer.music.play(-1 if loop else 0)
            elif sound_name in self.sounds and self.sounds[sound_name]:
                vol = 0.3 if progressive else 1.0
                self.sounds[sound_name].set_volume(vol)
                self.sounds[sound_name].play(loops=-1 if loop else 0)
                self.current_playing = self.sounds[sound_name]
            
            # If progressive fade is requested, schedule volume increase.
            # The scheduling is done in a non-blocking way in a GUI application.
            if progressive and loop:
                self._start_volume_fade()
        except Exception as e:
            print(f"Play error: {e}")
    
    def _start_volume_fade(self):
        """Increase the volume gradually.

        This method outlines a fade strategy: increase from 0.3 to 1.0 in steps.
        The actual scheduling is GUI-specific (e.g., root.after), so here it's
        implemented as a placeholder loop. In a GUI integration this should
        schedule steps non-blockingly.
        """
        def fade(step=0):
            if step < 10:
                vol = 0.3 + (step * 0.07)  # 0.3 -> 1.0 in 10 steps
                try:
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.set_volume(vol)
                    if self.current_playing:
                        self.current_playing.set_volume(vol)
                except:
                    pass
        
        # Note: In the original GUI code this would schedule successive calls
        # via tkinter's `after` so the fade does not block the UI thread.
        for i in range(10):
            # Schedule fade steps (in the real app, replace 'pass' with scheduling)
            pass
    
    def stop(self):
        """Stop any playing sounds and reset the playback state."""
        try:
            pygame.mixer.music.stop()
            if self.current_playing:
                self.current_playing.stop()
                self.current_playing = None
            pygame.mixer.stop()
        except:
            # Swallow errors to keep audio problems non-fatal
            pass

# ===================== STATS MANAGER =====================
# The StatsManager updates in-memory stats and persists them through ConfigManager.
class StatsManager:
    """Stores and updates productivity statistics.

    It depends on ConfigManager to persist history and aggregate stats.
    """
    def __init__(self, config_mgr):
        self.config = config_mgr
    
    def record_pomodoro(self, tag=None):
        """Record a completed pomodoro with optional tag.

        Steps:
        - Append a history item with date and timestamp
        - Increment aggregate counters: total pomodoros and minutes
        - Increment per-tag counters
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Add to history
        history = self.config.get("pomodoro_history", [])
        history.append({
            "date": today,
            "tag": tag,
            "timestamp": datetime.now().isoformat()
        })
        self.config.set("pomodoro_history", history)
        
        # Update stats
        stats = self.config.get("stats", {})
        stats["total_pomodoros"] = stats.get("total_pomodoros", 0) + 1
        stats["total_minutes"] = stats.get("total_minutes", 0) + 25
        
        if tag:
            by_tag = stats.get("sessions_by_tag", {})
            by_tag[tag] = by_tag.get(tag, 0) + 1
            stats["sessions_by_tag"] = by_tag
        
        # Persist updated stats
        self.config.set("stats", stats)
    
    def get_today_count(self):
        """Return the number of pomodoros recorded for today.

        This scans the history list and filters by today's date string.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        history = self.config.get("pomodoro_history", [])
        return sum(1 for p in history if p.get("date") == today)
    
    def get_week_count(self):
        """Return the number of pomodoros in the last 7 days.

        Note: Uses string comparison on ISO date strings which works when format is YYYY-MM-DD.
        """
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        history = self.config.get("pomodoro_history", [])
        return sum(1 for p in history if p.get("date", "") >= week_ago)
    
    def export_csv(self, filename):
        """Export the pomodoro history to a CSV file.

        Very simple implementation that writes three columns: date, tag, timestamp.
        """
        history = self.config.get("pomodoro_history", [])
        
        try:
            with open(filename, 'w') as f:
                f.write("date,tag,timestamp\n")
                for p in history:
                    f.write(f"{p.get('date','')},{p.get('tag','')},{p.get('timestamp','')}\n")
            return True
        except:
            return False

# ===================== MAIN APP =====================
# ClockPro is the primary GUI application class. It wires UI elements to logic
# and schedules periodic updates via tkinter's after method.
class ClockPro:
    """Main application class that builds the GUI and coordinates components.

    Responsibilities:
    - Build the Tkinter UI with multiple views (alarm, timer, stopwatch, pomodoro)
    - Wire UI events to logic callbacks
    - Periodically run a master clock method to update time, check alarms, and tick logic
    """
    def __init__(self, root):
        # Root is the Tk main window
        self.root = root
        self.root.title("Clock Pro")
        
        # Managers (single responsibility)
        self.config = ConfigManager()
        self.sound_mgr = SoundManager()
        self.notif_mgr = NotificationManager()
        self.stats_mgr = StatsManager(self.config)
        
        # Define a small set of built-in themes for quick UI styling
        self.themes = {
            "Matrix": {"bg": "#000000", "fg": "#00FF00", "accent": "#008800"},
            "Cyber": {"bg": "#0a0a0a", "fg": "#00d4ff", "accent": "#0080ff"},
            "Fire": {"bg": "#1a0000", "fg": "#ff3300", "accent": "#cc0000"},
            "Purple": {"bg": "#0d0010", "fg": "#da00ff", "accent": "#8800cc"},
            "Ocean": {"bg": "#001a33", "fg": "#00ffff", "accent": "#0099cc"}
        }
        
        # Logic objects: instantiate timer/stopwatch/pomodoro with callbacks that update UI
        self.timer = TimerLogic(
            on_update=self.on_timer_update,
            on_finish=self.on_timer_finish
        )
        self.stopwatch = StopwatchLogic(on_update=self.on_stopwatch_update)
        self.pomodoro = PomodoroLogic(
            on_update=self.on_pomodoro_update,
            on_phase_complete=self.on_pomodoro_complete
        )
        
        # Load persistent state into runtime variables
        self.current_sound = self.config.get("sound", "Beep")
        self.time_format_24h = self.config.get("time_format_24h", True)
        self.time_offset = self.config.get("time_offset", 0)
        self.window_mode = self.config.get("window_mode", "normal")
        self.current_view = None
        self.alarm_widgets = []
        self.current_pomo_tag = None
        
        # Setup UI layout and behavior
        self._set_window_size()
        self._setup_ui()
        self._setup_keybindings()
        self._apply_theme()
        self._load_alarms()
        self._start_master_clock()  # schedule the recurring updates
    
    def _set_window_size(self):
        """Set the initial window geometry based on saved mode.

        Keeps the window non-resizable and uses three size presets.
        """
        sizes = {
            "mini": "250x120",
            "normal": "480x380",
            "full": "600x520"
        }
        self.root.geometry(sizes.get(self.window_mode, "480x380"))
        self.root.resizable(False, False)
    
    def _setup_ui(self):
        """Create the main UI structure.

        The UI consists of:
        - A top bar with theme, sound, format, mode, and stats controls
        - A clock display (time/date)
        - Navigation buttons that show different functional views
        - Views: alarm, timer, stopwatch, pomodoro (created by helper methods)
        """
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        # Top bar with controls
        top = tk.Frame(main, height=24)
        top.pack(fill=tk.X, pady=(0, 4))
        top.pack_propagate(False)
        
        # Theme selector (ttk combobox for consistent look)
        self.theme_var = tk.StringVar(value=self.config.get("theme", "Matrix"))
        ttk.Combobox(top, textvariable=self.theme_var, values=list(self.themes.keys()),
                    width=7, state="readonly", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        # Trace variable changes to update theme live
        self.theme_var.trace('w', lambda *a: self._change_theme())
        
        # Sound selector
        self.sound_var = tk.StringVar(value=self.current_sound)
        ttk.Combobox(top, textvariable=self.sound_var, 
                    values=["Beep", "Alert", "Chime", "Bell", "Alarm", "Custom"],
                    width=7, state="readonly", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        self.sound_var.trace('w', lambda *a: self._change_sound())
        
        # 24/12 hour format toggle button
        self.fmt_btn = tk.Button(top, text="24h" if self.time_format_24h else "12h", 
                                command=self._toggle_format,
                                font=('Arial', 8, 'bold'), relief='flat', padx=6, pady=1)
        self.fmt_btn.pack(side=tk.LEFT, padx=4)
        
        # Mode selector: cycles between mini/normal/full
        mode_btn = tk.Button(top, text="□", command=self._cycle_window_mode,
                            font=('Arial', 9), relief='flat', padx=4, pady=0)
        mode_btn.pack(side=tk.LEFT, padx=2)
        
        # Stats button opens a separate window with productivity statistics
        stats_btn = tk.Button(top, text="📊", command=self._show_stats,
                             font=('Arial', 9), relief='flat', padx=4, pady=0)
        stats_btn.pack(side=tk.LEFT, padx=2)
        
        # Keep-on-top toggle button
        self.top_btn = tk.Button(top, text="📌", command=self._toggle_top,
                                font=('Arial', 9), relief='flat', padx=4, pady=0)
        self.top_btn.pack(side=tk.RIGHT)
        
        # Main clock display (large font)
        clock_size = 32 if self.window_mode == "mini" else 46
        self.clock_lbl = tk.Label(main, font=('Arial', clock_size, 'bold'), relief='flat')
        self.clock_lbl.pack(pady=(0, 2))
        
        # Date label shown in non-mini modes
        if self.window_mode != "mini":
            self.date_lbl = tk.Label(main, font=('Arial', 11), relief='flat')
            self.date_lbl.pack()
        
        # Navigation and content area are hidden in mini mode to save space
        if self.window_mode != "mini":
            nav = tk.Frame(main)
            nav.pack(pady=6)
            
            self.nav_btns = {}
            # Navigation buttons map an emoji to a view name
            for emoji, view in [("🕐", "alarm"), ("⏱️", "timer"), ("⏲️", "stopwatch"), ("🍅", "pomodoro")]:
                btn = tk.Button(nav, text=emoji, command=lambda v=view: self._toggle_view(v),
                               font=('Arial', 14), relief='flat', bd=0, padx=10, pady=3)
                btn.pack(side=tk.LEFT, padx=1)
                self.nav_btns[view] = btn
            
            # Content frame where each view will be packed/unpacked
            height = 200 if self.window_mode == "full" else 140
            self.content = tk.Frame(main, height=height)
            self.content.pack(fill=tk.BOTH, expand=True, pady=4)
            self.content.pack_propagate(False)
            
            # Build each separate view inside the content area
            self.views = {}
            self._create_alarm_view()
            self._create_timer_view()
            self._create_stopwatch_view()
            self._create_pomodoro_view()
    
    def _create_alarm_view(self):
        """Construct the alarm management UI.

        The view includes:
        - A scrollable list of alarms
        - Inputs to add a new alarm (hour/minute and label)
        - Each alarm can be enabled/disabled or deleted
        """
        f = tk.Frame(self.content)
        
        # Alarm list container
        list_frame = tk.Frame(f)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        
        # Make the alarm list scrollable using a Canvas + internal Frame pattern
        canvas = tk.Canvas(list_frame, height=80)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.alarm_list_frame = tk.Frame(canvas)
        
        # Keep canvas scroll region synced with the internal frame size
        self.alarm_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Add the internal frame into the canvas
        canvas.create_window((0, 0), window=self.alarm_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Section to add a new alarm
        add_frame = tk.Frame(f)
        add_frame.pack(pady=4)
        
        time_f = tk.Frame(add_frame)
        time_f.pack(side=tk.LEFT, padx=4)
        
        # Hour and minute spinboxes allow the user to choose the alarm time
        self.alarm_h = tk.Spinbox(time_f, from_=0, to=23, width=2,
                                 font=('Arial', 10), wrap=True, justify='center')
        self.alarm_h.pack(side=tk.LEFT, padx=1)
        tk.Label(time_f, text=":").pack(side=tk.LEFT)
        
        self.alarm_m = tk.Spinbox(time_f, from_=0, to=59, width=2,
                                 font=('Arial', 10), wrap=True, justify='center')
        self.alarm_m.pack(side=tk.LEFT, padx=1)
        
        # Label input for the alarm text
        self.alarm_label_entry = tk.Entry(add_frame, width=12, font=('Arial', 9))
        self.alarm_label_entry.pack(side=tk.LEFT, padx=4)
        self.alarm_label_entry.insert(0, "Label")
        
        # Button to add the new alarm to config and UI
        tk.Button(add_frame, text="+ Add", command=self._add_alarm,
                 font=('Arial', 9), relief='flat', padx=8, pady=2).pack(side=tk.LEFT)
        
        self.views["alarm"] = f
    
    def _create_timer_view(self):
        """Construct a simple countdown timer UI with quick presets and custom input."""
        f = tk.Frame(self.content)
        
        # Quick preset buttons (configured from user settings)
        preset_f = tk.Frame(f)
        preset_f.pack(pady=4)
        
        tk.Label(preset_f, text="Quick:", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        
        presets = self.config.get("timer_presets", [1, 5, 10, 15, 25, 45])
        for mins in presets:
            tk.Button(preset_f, text=f"{mins}m", 
                     command=lambda m=mins: self._start_timer_preset(m),
                     font=('Arial', 8), relief='flat', padx=6, pady=2).pack(side=tk.LEFT, padx=1)
        
        # Custom minute/second input
        input_f = tk.Frame(f)
        input_f.pack(pady=4)
        
        tk.Label(input_f, text="Min", font=('Arial', 8)).grid(row=0, column=0)
        self.timer_min = tk.Spinbox(input_f, from_=0, to=99, width=3,
                                   font=('Arial', 12), justify='center')
        self.timer_min.grid(row=1, column=0, padx=2)
        self.timer_min.delete(0, tk.END)
        self.timer_min.insert(0, "5")
        
        tk.Label(input_f, text="Sec", font=('Arial', 8)).grid(row=0, column=1)
        self.timer_sec = tk.Spinbox(input_f, from_=0, to=59, width=3,
                                   font=('Arial', 12), justify='center')
        self.timer_sec.grid(row=1, column=1, padx=2)
        self.timer_sec.delete(0, tk.END)
        self.timer_sec.insert(0, "0")
        
        # Display label shows remaining time during countdown
        self.timer_lbl = tk.Label(f, text="00:00", font=('Arial', 36, 'bold'))
        self.timer_lbl.pack(pady=4)
        
        # Controls: start, pause, stop
        btn_f = tk.Frame(f)
        btn_f.pack()
        
        self.timer_start_btn = tk.Button(btn_f, text="▶", command=self._start_timer,
                                        font=('Arial', 10), relief='flat', padx=10, pady=2)
        self.timer_start_btn.pack(side=tk.LEFT, padx=1)
        
        self.timer_pause_btn = tk.Button(btn_f, text="⏸", command=lambda: self.timer.pause(),
                                        font=('Arial', 10), relief='flat', padx=10, pady=2, state='disabled')
        self.timer_pause_btn.pack(side=tk.LEFT, padx=1)
        
        self.timer_stop_btn = tk.Button(btn_f, text="⏹", command=self._stop_timer,
                                       font=('Arial', 10), relief='flat', padx=10, pady=2, state='disabled')
        self.timer_stop_btn.pack(side=tk.LEFT, padx=1)
        
        self.views["timer"] = f
    
    def _create_stopwatch_view(self):
        """Build a simple stopwatch UI with start/pause/reset actions."""
        f = tk.Frame(self.content)
        
        self.stopwatch_lbl = tk.Label(f, text="00:00:00", font=('Arial', 38, 'bold'))
        self.stopwatch_lbl.pack(pady=20)
        
        btn_f = tk.Frame(f)
        btn_f.pack()
        
        # Start uses the logic object's start method; UI state is updated by the master clock loop
        self.sw_start_btn = tk.Button(btn_f, text="▶", command=lambda: self.stopwatch.start(),
                                     font=('Arial', 10), relief='flat', padx=12, pady=4)
        self.sw_start_btn.pack(side=tk.LEFT, padx=2)
        
        self.sw_pause_btn = tk.Button(btn_f, text="⏸", command=lambda: self.stopwatch.pause(),
                                     font=('Arial', 10), relief='flat', padx=12, pady=4, state='disabled')
        self.sw_pause_btn.pack(side=tk.LEFT, padx=2)
        
        self.sw_reset_btn = tk.Button(btn_f, text="⟲", command=lambda: self.stopwatch.reset(),
                                     font=('Arial', 10), relief='flat', padx=12, pady=4)
        self.sw_reset_btn.pack(side=tk.LEFT, padx=2)
        
        self.views["stopwatch"] = f
    
    def _create_pomodoro_view(self):
        """Create the Pomodoro UI, including tag selector and controls.

        This view shows current time left, status (work/break), and today's/week count.
        """
        f = tk.Frame(self.content)
        
        # Tag selector gives a quick way to label pomodoro sessions for stats
        tag_f = tk.Frame(f)
        tag_f.pack(pady=4)
        
        tk.Label(tag_f, text="Tag:", font=('Arial', 9)).pack(side=tk.LEFT, padx=2)
        
        self.pomo_tag_var = tk.StringVar(value="")
        tags = ["🧬 Bio", "📊 Data", "📖 Reading", "✍️ Writing", "💻 Code", "🎓 Study"]
        ttk.Combobox(tag_f, textvariable=self.pomo_tag_var, values=tags,
                    width=12, font=('Arial', 8)).pack(side=tk.LEFT)
        
        self.pomo_lbl = tk.Label(f, text="25:00", font=('Arial', 40, 'bold'))
        self.pomo_lbl.pack(pady=8)
        
        self.pomo_status = tk.Label(f, text="🍅 Work (25min)", font=('Arial', 11, 'bold'))
        self.pomo_status.pack()
        
        btn_f = tk.Frame(f)
        btn_f.pack(pady=6)
        
        self.pomo_start_btn = tk.Button(btn_f, text="▶", command=self._start_pomodoro,
                                       font=('Arial', 10), relief='flat', padx=10, pady=2)
        self.pomo_start_btn.pack(side=tk.LEFT, padx=1)
        
        self.pomo_pause_btn = tk.Button(btn_f, text="⏸", command=lambda: self.pomodoro.pause(),
                                       font=('Arial', 10), relief='flat', padx=10, pady=2, state='disabled')
        self.pomo_pause_btn.pack(side=tk.LEFT, padx=1)
        
        self.pomo_skip_btn = tk.Button(btn_f, text="⏭", command=lambda: self.pomodoro.skip(),
                                      font=('Arial', 10), relief='flat', padx=10, pady=2)
        self.pomo_skip_btn.pack(side=tk.LEFT, padx=1)
        
        # Show today's and week's completed pomodoro counts (obtained from StatsManager)
        today = self.stats_mgr.get_today_count()
        week = self.stats_mgr.get_week_count()
        self.pomo_count_lbl = tk.Label(f, text=f"Today: {today} | Week: {week}", font=('Arial', 9))
        self.pomo_count_lbl.pack()
        
        self.views["pomodoro"] = f
    
    def _setup_keybindings(self):
        """Bind keyboard shortcuts to common actions.

        Examples:
        - Space toggles start/pause for timer/pomodoro/stopwatch depending on view
        - 'r' resets stopwatch
        - Numeric keys switch views quickly
        - 'p' plays the current sound for debugging
        """
        self.root.bind('<space>', lambda e: self._key_space())
        self.root.bind('r', lambda e: self.stopwatch.reset())
        self.root.bind('R', lambda e: self.stopwatch.reset())
        self.root.bind('<Escape>', lambda e: self._hide_current_view())
        self.root.bind('1', lambda e: self._toggle_view('alarm'))
        self.root.bind('2', lambda e: self._toggle_view('timer'))
        self.root.bind('3', lambda e: self._toggle_view('stopwatch'))
        self.root.bind('4', lambda e: self._toggle_view('pomodoro'))
        self.root.bind('p', lambda e: self.sound_mgr.play(self.current_sound))
        self.root.bind('P', lambda e: self.sound_mgr.play(self.current_sound))
    
    def _key_space(self):
        """Spacebar behavior contextually starts/pauses current mode."""
        if self.current_view == "timer":
            if self.timer.running:
                self.timer.pause()
            else:
                self._start_timer()
        elif self.current_view == "pomodoro":
            if self.pomodoro.running:
                self.pomodoro.pause()
            else:
                self._start_pomodoro()
        elif self.current_view == "stopwatch":
            if self.stopwatch.running:
                self.stopwatch.pause()
            else:
                self.stopwatch.start()
    
    def _hide_current_view(self):
        """Hide the currently visible view frame if any."""
        if self.current_view and self.current_view in self.views:
            self.views[self.current_view].pack_forget()
            self.nav_btns[self.current_view].config(relief='flat')
            self.current_view = None
    
    def _toggle_view(self, view_name):
        """Show or hide a named view in the content area.

        Also updates navigation button states (sunken/flat).
        """
        if self.window_mode == "mini":
            # Views are not displayed in mini mode to keep UI compact
            return
        
        if self.current_view == view_name:
            self.views[view_name].pack_forget()
            self.current_view = None
            self.nav_btns[view_name].config(relief='flat')
        else:
            if self.current_view:
                self.views[self.current_view].pack_forget()
                self.nav_btns[self.current_view].config(relief='flat')
            
            self.views[view_name].pack(fill=tk.BOTH, expand=True)
            self.current_view = view_name
            self.nav_btns[view_name].config(relief='sunken')
    
    def _load_alarms(self):
        """Load saved alarms from configuration and create UI widgets for them."""
        alarms = self.config.get("alarms", [])
        for alarm in alarms:
            self._add_alarm_widget(alarm)
    
    def _add_alarm(self):
        """Create a new alarm from UI inputs and persist it.

        Alarm times are stored as HH:MM:SS strings to make comparison easy.
        """
        # Use spinbox values for hour/minute, formatting to two digits
        h = self.alarm_h.get().zfill(2)
        m = self.alarm_m.get().zfill(2)
        label = self.alarm_label_entry.get()
        
        alarm = {
            "time": f"{h}:{m}:00",
            "label": label,
            "enabled": True
        }
        
        # Save to config and add widget to UI
        alarms = self.config.get("alarms", [])
        alarms.append(alarm)
        self.config.set("alarms", alarms)
        
        self._add_alarm_widget(alarm)
    
    def _add_alarm_widget(self, alarm):
        """Add a visual representation of an alarm into the scrollable alarm list.

        Each alarm row includes:
        - a checkbox to enable/disable the alarm
        - a label showing time and optional text
        - a delete button
        """
        f = tk.Frame(self.alarm_list_frame)
        f.pack(fill=tk.X, pady=2)
        
        var = tk.BooleanVar(value=alarm.get("enabled", True))
        
        cb = tk.Checkbutton(f, variable=var, 
                           command=lambda: self._toggle_alarm(alarm, var.get()))
        cb.pack(side=tk.LEFT)
        
        # Show only hours:minutes for compactness
        tk.Label(f, text=alarm["time"][:5], font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text=alarm.get("label", ""), font=('Arial', 9)).pack(side=tk.LEFT, padx=4)
        
        tk.Button(f, text="×", command=lambda: self._delete_alarm(alarm, f),
                 font=('Arial', 10), relief='flat', padx=4).pack(side=tk.RIGHT)
        
        # Keep a reference so we can update/remove later
        self.alarm_widgets.append((alarm, f, var))
    
    def _toggle_alarm(self, alarm, enabled):
        """Enable or disable an alarm and persist the change.

        This modifies the alarm object and writes the entire alarms list back to config.
        """
        alarm["enabled"] = enabled
        alarms = self.config.get("alarms", [])
        # The alarms list holds references to the same alarm dicts, so just save it.
        self.config.set("alarms", alarms)
    
    def _delete_alarm(self, alarm, widget):
        """Remove an alarm both from the config and the UI."""
        alarms = self.config.get("alarms", [])
        if alarm in alarms:
            alarms.remove(alarm)
            self.config.set("alarms", alarms)
        
        widget.destroy()
        self.alarm_widgets = [(a, w, v) for a, w, v in self.alarm_widgets if w != widget]
    
    def _start_timer_preset(self, minutes):
        """Start a timer using a preset number of minutes."""
        self.timer.start(minutes * 60)
    
    def _start_timer(self):
        """Start timer using values read from the minute/second spinboxes."""
        mins = int(self.timer_min.get())
        secs = int(self.timer_sec.get())
        self.timer.start(mins * 60 + secs)
    
    def _stop_timer(self):
        """Stop the timer and reset the UI label."""
        self.timer.stop()
        self.timer_lbl.config(text="00:00")
    
    def _start_pomodoro(self):
        """Start a pomodoro session using the selected tag."""
        tag = self.pomo_tag_var.get() if self.pomo_tag_var.get() else None
        self.current_pomo_tag = tag
        self.pomodoro.start(tag)
    
    def _cycle_window_mode(self):
        """Toggle between mini / normal / full window modes.

        This rebuilds the UI to reflect the chosen mode size and visibility.
        """
        modes = ["mini", "normal", "full"]
        idx = modes.index(self.window_mode)
        self.window_mode = modes[(idx + 1) % len(modes)]
        self.config.set("window_mode", self.window_mode)
        
        # Rebuild the entire UI to apply new layout settings
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self._set_window_size()
        self._setup_ui()
        self._setup_keybindings()
        self._apply_theme()
        self._load_alarms()
    
    def _show_stats(self):
        """Open a separate statistics window displaying productivity aggregates.

        This method demonstrates creating modal-like Toplevel windows for info.
        """
        stats_win = tk.Toplevel(self.root)
        stats_win.title("Statistics")
        stats_win.geometry("400x300")
        
        stats = self.config.get("stats", {})
        
        tk.Label(stats_win, text="📊 Productivity Stats", 
                font=('Arial', 16, 'bold')).pack(pady=10)
        
        total = stats.get("total_pomodoros", 0)
        hours = stats.get("total_minutes", 0) / 60
        today = self.stats_mgr.get_today_count()
        week = self.stats_mgr.get_week_count()
        
        # Multiline info string demonstrates simple string formatting
        info = f"""
Total Pomodoros: {total} 🍅
Total Focus Time: {hours:.1f} hours
Today: {today} 🍅
This Week: {week} 🍅
Avg per Day: {week/7:.1f} 🍅
        """
        
        tk.Label(stats_win, text=info, font=('Arial', 12), justify='left').pack(pady=10)
        
        # Show per-tag breakdown if available
        by_tag = stats.get("sessions_by_tag", {})
        if by_tag:
            tk.Label(stats_win, text="By Tag:", font=('Arial', 12, 'bold')).pack()
            for tag, count in sorted(by_tag.items(), key=lambda x: x[1], reverse=True):
                tk.Label(stats_win, text=f"{tag}: {count} sessions", 
                        font=('Arial', 10)).pack()
        
        # Provide an export button to save CSV (delegates to StatsManager)
        tk.Button(stats_win, text="📥 Export CSV", 
                 command=self._export_stats,
                 font=('Arial', 10, 'bold'), padx=20, pady=5).pack(pady=20)
    
    def _export_stats(self):
        """Ask the user for a filename and export the stats to CSV."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            if self.stats_mgr.export_csv(filename):
                messagebox.showinfo("Success", f"Exported to:\n{filename}")
            else:
                messagebox.showerror("Error", "Export failed")
    
    def _toggle_format(self):
        """Toggle between 24-hour and 12-hour display formats and persist choice."""
        self.time_format_24h = not self.time_format_24h
        self.fmt_btn.config(text="24h" if self.time_format_24h else "12h")
        self.config.set("time_format_24h", self.time_format_24h)
    
    def _toggle_top(self):
        """Toggle the window 'always on top' attribute."""
        current = self.root.attributes('-topmost')
        self.root.attributes('-topmost', not current)
        self.top_btn.config(relief='sunken' if not current else 'flat')
    
    def _change_sound(self):
        """Change the alarm sound selection; allow selecting a custom file."""
        self.current_sound = self.sound_var.get()
        self.config.set("sound", self.current_sound)
        
        if self.current_sound == "Custom":
            path = filedialog.askopenfilename(
                title="Select Sound",
                filetypes=[("Audio", "*.wav *.mp3 *.ogg *.aiff"), ("All", "*.*")]
            )
            if path:
                self.sound_mgr.custom_sound = path
            else:
                # Revert to default if no file chosen
                self.sound_var.set("Beep")
                self.current_sound = "Beep"
    
    def _change_theme(self):
        """Persist theme selection and re-apply visual styles."""
        theme = self.theme_var.get()
        self.config.set("theme", theme)
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply colors to the root window and try to propagate them to children.

        The helper uses recursion to set bg/fg of Frame/Label/Button widgets.
        The function is defensive and ignores widget types it cannot style.
        """
        t = self.themes[self.theme_var.get()]
        self.root.configure(bg=t["bg"])
        
        def apply_recursive(w):
            try:
                if isinstance(w, (tk.Frame, tk.Label)):
                    w.configure(bg=t["bg"])
                    if isinstance(w, tk.Label):
                        w.configure(fg=t["fg"])
                elif isinstance(w, tk.Button):
                    w.configure(bg=t["bg"], fg=t["fg"],
                               activebackground=t["accent"], activeforeground=t["fg"])
                for child in w.winfo_children():
                    apply_recursive(child)
            except:
                # Ignore styling errors for widgets that don't accept those options
                pass
        
        apply_recursive(self.root)
    
    def _start_master_clock(self):
        """Main loop called once per second using tkinter's after.

        Responsibilities each tick:
        - Update displayed current time and date
        - Check alarms by comparing HH:MM:SS strings
        - Tick each logic object (timer/stopwatch/pomodoro)
        - Update UI controls state to reflect running/paused states
        - Reschedule itself to run after 1000 ms (1 second)
        """
        # Get current time with user-configured offset
        now = datetime.now() + timedelta(seconds=self.time_offset)
        time_str = now.strftime('%H:%M:%S' if self.time_format_24h else '%I:%M:%S %p')
        self.clock_lbl.config(text=time_str)
        
        if self.window_mode != "mini" and hasattr(self, 'date_lbl'):
            self.date_lbl.config(text=now.strftime('%d/%m - %A'))
        
        # Check alarms saved in config
        current_time = now.strftime('%H:%M:%S')
        alarms = self.config.get("alarms", [])
        for alarm in alarms:
            # If an enabled alarm matches the exact second, trigger it
            if alarm.get("enabled") and alarm["time"] == current_time:
                self._trigger_alarm(alarm)
                alarm["enabled"] = False  # Auto-disable to avoid repeating every second
                self.config.set("alarms", alarms)
        
        # Advance logic objects by one second
        self.timer.tick()
        self.stopwatch.tick()
        self.pomodoro.tick()
        
        # Update control states for UI (buttons enabled/disabled as appropriate)
        if self.window_mode != "mini":
            self._update_timer_ui()
            self._update_stopwatch_ui()
            self._update_pomodoro_ui()
        
        # Schedule the next tick after 1 second (1000 ms)
        self.root.after(1000, self._start_master_clock)
    
    def _trigger_alarm(self, alarm):
        """Notify user with sound and notification when an alarm goes off."""
        label = alarm.get("label", "Alarm")
        self._play_alarm("🔔 Alarm!", f"{alarm['time'][:5]} - {label}")
    
    # Callback methods invoked by logic objects to update the UI
    def on_timer_update(self, remaining):
        """Update the timer label with MM:SS format."""
        if hasattr(self, 'timer_lbl'):
            mins, secs = divmod(remaining, 60)
            self.timer_lbl.config(text=f"{mins:02d}:{secs:02d}")
    
    def on_timer_finish(self):
        """Handler called when timer finishes its countdown."""
        self._play_alarm("⏰ Timer", "Time's up!")
        self._stop_timer()
    
    def on_stopwatch_update(self, elapsed):
        """Update the stopwatch label using HH:MM:SS format."""
        if hasattr(self, 'stopwatch_lbl'):
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            self.stopwatch_lbl.config(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
    
    def on_pomodoro_update(self, time, phase):
        """Update the pomodoro label showing remaining MM:SS during a phase."""
        if hasattr(self, 'pomo_lbl'):
            mins, secs = divmod(time, 60)
            self.pomo_lbl.config(text=f"{mins:02d}:{secs:02d}")
    
    def on_pomodoro_complete(self, phase, count, tag):
        """Handle transitions when a pomodoro phase completes (work or break).

        During a work->break transition we:
        - update UI status text
        - record a pomodoro in stats
        - show a notification + play alarm sound
        After break completes we notify the user the cycle is complete.
        """
        if phase == "work":
            if hasattr(self, 'pomo_status'):
                self.pomo_status.config(text="☕ Break (5min)")
            self.stats_mgr.record_pomodoro(tag)
            self._play_alarm("🍅 Pomodoro", f"Work done! Break time.\n{tag or ''}\nTotal: {count} 🍅")
            
            # Refresh counts in the pomodoro view
            if hasattr(self, 'pomo_count_lbl'):
                today = self.stats_mgr.get_today_count()
                week = self.stats_mgr.get_week_count()
                self.pomo_count_lbl.config(text=f"Today: {today} | Week: {week}")
        else:
            if hasattr(self, 'pomo_status'):
                self.pomo_status.config(text="✅ Complete!")
            self._play_alarm("🍅 Pomodoro", "Break over!")
    
    # UI update helpers to enable/disable buttons based on logic state
    def _update_timer_ui(self):
        """Update timer-related buttons depending on running/paused state."""
        if hasattr(self, 'timer_start_btn'):
            if self.timer.running:
                self.timer_start_btn.config(state='disabled')
                # Show pause as play (▶) when paused, otherwise a pause icon
                self.timer_pause_btn.config(state='normal', text="▶" if self.timer.paused else "⏸")
                self.timer_stop_btn.config(state='normal')
            else:
                self.timer_start_btn.config(state='normal')
                self.timer_pause_btn.config(state='disabled')
                self.timer_stop_btn.config(state='disabled')
    
    def _update_stopwatch_ui(self):
        """Update stopwatch buttons depending on running/paused state."""
        if hasattr(self, 'sw_start_btn'):
            if self.stopwatch.running:
                self.sw_start_btn.config(state='disabled')
                self.sw_pause_btn.config(state='normal', text="▶" if self.stopwatch.paused else "⏸")
            else:
                self.sw_start_btn.config(state='normal')
                self.sw_pause_btn.config(state='disabled')
    
    def _update_pomodoro_ui(self):
        """Update pomodoro buttons depending on running/paused state."""
        if hasattr(self, 'pomo_start_btn'):
            if self.pomodoro.running:
                self.pomo_start_btn.config(state='disabled')
                self.pomo_pause_btn.config(state='normal', text="▶" if self.pomodoro.paused else "⏸")
            else:
                self.pomo_start_btn.config(state='normal')
                self.pomo_pause_btn.config(state='disabled')
    
    def _play_alarm(self, title, msg):
        """Play alarm sound, show a native notification, and display a messagebox.

        Flow:
        - Start playing a looping sound with progressive volume
        - Show a platform notification (non-blocking ideally)
        - Show a blocking messagebox to require user dismissal
        - Stop sound playback after the user dismisses the messagebox
        """
        self.sound_mgr.play(self.current_sound, loop=True, progressive=True)
        self.notif_mgr.show(title, msg)
        # messagebox.showinfo is blocking until user clicks OK, holding alarm sound until then.
        messagebox.showinfo(title, msg)
        self.sound_mgr.stop()


# Standard boilerplate to run the app when this file is executed directly.
# Students: the `if __name__ == "__main__":` guard prevents this block from running
# when the module is imported for testing or reuse.
if __name__ == "__main__":
    root = tk.Tk()
    app = ClockPro(root)
    # Start the tkinter main loop which handles events and scheduled `after` callbacks.
    root.mainloop()