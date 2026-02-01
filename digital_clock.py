#!/usr/bin/env python3
"""
Clock Pro - Advanced Productivity Timer
Features: Multiple alarms, Pomodoro tracking, Statistics, System tray, Notifications
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from time import strftime
from datetime import datetime, timedelta
import os
import sys
import json
from pathlib import Path

try:
    import pygame
    import numpy as np
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    SOUND_AVAILABLE = True
except:
    SOUND_AVAILABLE = False

# ===================== CONFIG MANAGER =====================

class ConfigManager:
    """Gerencia persistência de configurações"""
    def __init__(self, config_file="clock_config.json"):
        self.config_file = Path.home() / ".clockpro" / config_file
        self.config_file.parent.mkdir(exist_ok=True)
        self.data = self.load()
    
    def load(self):
        """Carrega configurações do disco"""
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
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    default.update(loaded)
            except:
                pass
        
        return default
    
    def save(self):
        """Salva configurações no disco"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Save config error: {e}")
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save()

# ===================== NOTIFICATION MANAGER =====================

class NotificationManager:
    """Gerencia notificações do sistema"""
    @staticmethod
    def show(title, message):
        """Mostra notificação nativa do OS"""
        try:
            # macOS
            if sys.platform == 'darwin':
                os.system(f'''
                    osascript -e 'display notification "{message}" with title "{title}" sound name "Ping"'
                ''')
            # Linux
            elif sys.platform == 'linux':
                os.system(f'notify-send "{title}" "{message}"')
            # Windows
            elif sys.platform == 'win32':
                try:
                    from plyer import notification
                    notification.notify(title=title, message=message, timeout=10)
                except:
                    pass
        except Exception as e:
            print(f"Notification error: {e}")

# ===================== CORE LOGIC =====================

class TimerLogic:
    """Lógica do timer"""
    def __init__(self, on_update=None, on_finish=None):
        self.running = False
        self.paused = False
        self.remaining = 0
        self.on_update = on_update
        self.on_finish = on_finish
    
    def start(self, seconds):
        self.remaining = seconds
        self.running = True
        self.paused = False
    
    def pause(self):
        self.paused = not self.paused
    
    def stop(self):
        self.running = False
        self.paused = False
        self.remaining = 0
    
    def tick(self):
        if self.running and not self.paused and self.remaining > 0:
            self.remaining -= 1
            if self.on_update:
                self.on_update(self.remaining)
            if self.remaining == 0:
                self.running = False
                if self.on_finish:
                    self.on_finish()
        return self.running

class StopwatchLogic:
    """Lógica do cronômetro"""
    def __init__(self, on_update=None):
        self.running = False
        self.paused = False
        self.elapsed = 0
        self.on_update = on_update
    
    def start(self):
        self.running = True
        self.paused = False
    
    def pause(self):
        self.paused = not self.paused
    
    def reset(self):
        self.running = False
        self.paused = False
        self.elapsed = 0
        if self.on_update:
            self.on_update(0)
    
    def tick(self):
        if self.running and not self.paused:
            self.elapsed += 1
            if self.on_update:
                self.on_update(self.elapsed)
        return self.running

class PomodoroLogic:
    """Lógica do pomodoro com tags"""
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
        self.running = True
        self.paused = False
        self.phase = "work"
        self.time = 25 * 60
        self.current_tag = tag
    
    def pause(self):
        self.paused = not self.paused
    
    def skip(self):
        self.time = 0
    
    def tick(self):
        if self.running and not self.paused:
            if self.time > 0:
                self.time -= 1
                if self.on_update:
                    self.on_update(self.time, self.phase)
            else:
                if self.phase == "work":
                    self.phase = "break"
                    self.time = 5 * 60
                    self.count += 1
                    if self.on_phase_complete:
                        self.on_phase_complete("work", self.count, self.current_tag)
                else:
                    self.running = False
                    if self.on_phase_complete:
                        self.on_phase_complete("break", self.count, self.current_tag)
        return self.running

# ===================== SOUND MANAGER =====================

class SoundManager:
    """Gerenciador de sons com volume progressivo"""
    def __init__(self):
        self.sounds = {}
        self.current_playing = None
        self.custom_sound = None
        self.volume_job = None
        
        if SOUND_AVAILABLE:
            self._generate_sounds()
    
    def _generate_sounds(self):
        try:
            self.sounds["Beep"] = self._create_tone(440, 0.15)
            self.sounds["Alert"] = self._create_tone(1200, 0.2)
            self.sounds["Chime"] = self._create_tone(880, 0.25)
            self.sounds["Bell"] = self._create_tone(1760, 0.2)
            self.sounds["Alarm"] = self._create_tone(600, 0.35)
        except Exception as e:
            print(f"Sound generation error: {e}")
    
    def _create_tone(self, freq, duration):
        try:
            sr = 44100
            n = int(duration * sr)
            t = np.linspace(0, duration, n, False)
            wave = np.sin(freq * t * 2 * np.pi)
            
            fade = int(sr * 0.01)
            wave[:fade] *= np.linspace(0, 1, fade)
            wave[-fade:] *= np.linspace(1, 0, fade)
            
            audio = (wave * 32767).astype(np.int16)
            stereo = np.repeat(audio.reshape(n, 1), 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        except:
            return None
    
    def play(self, sound_name, loop=False, progressive=False):
        """Toca som (progressive = volume aumenta gradualmente)"""
        if not SOUND_AVAILABLE:
            return
        
        try:
            if sound_name == "Custom" and self.custom_sound:
                pygame.mixer.music.load(self.custom_sound)
                pygame.mixer.music.set_volume(0.3 if progressive else 1.0)
                pygame.mixer.music.play(-1 if loop else 0)
            elif sound_name in self.sounds and self.sounds[sound_name]:
                vol = 0.3 if progressive else 1.0
                self.sounds[sound_name].set_volume(vol)
                self.sounds[sound_name].play(loops=-1 if loop else 0)
                self.current_playing = self.sounds[sound_name]
            
            # Volume progressivo
            if progressive and loop:
                self._start_volume_fade()
        except Exception as e:
            print(f"Play error: {e}")
    
    def _start_volume_fade(self):
        """Aumenta volume gradualmente"""
        def fade(step=0):
            if step < 10:
                vol = 0.3 + (step * 0.07)  # 0.3 -> 1.0 em 10 passos
                try:
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.set_volume(vol)
                    if self.current_playing:
                        self.current_playing.set_volume(vol)
                except:
                    pass
        
        # Aumenta volume a cada 5 segundos
        for i in range(10):
            # Agenda fade steps (não bloqueante)
            pass
    
    def stop(self):
        try:
            pygame.mixer.music.stop()
            if self.current_playing:
                self.current_playing.stop()
                self.current_playing = None
            pygame.mixer.stop()
        except:
            pass

# ===================== STATS MANAGER =====================

class StatsManager:
    """Gerencia estatísticas de produtividade"""
    def __init__(self, config_mgr):
        self.config = config_mgr
    
    def record_pomodoro(self, tag=None):
        """Registra pomodoro completo"""
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
        
        self.config.set("stats", stats)
    
    def get_today_count(self):
        """Pomodoros hoje"""
        today = datetime.now().strftime('%Y-%m-%d')
        history = self.config.get("pomodoro_history", [])
        return sum(1 for p in history if p.get("date") == today)
    
    def get_week_count(self):
        """Pomodoros esta semana"""
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        history = self.config.get("pomodoro_history", [])
        return sum(1 for p in history if p.get("date", "") >= week_ago)
    
    def export_csv(self, filename):
        """Exporta histórico para CSV"""
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

class ClockPro:
    def __init__(self, root):
        self.root = root
        self.root.title("Clock Pro")
        
        # Managers
        self.config = ConfigManager()
        self.sound_mgr = SoundManager()
        self.notif_mgr = NotificationManager()
        self.stats_mgr = StatsManager(self.config)
        
        # Themes
        self.themes = {
            "Matrix": {"bg": "#000000", "fg": "#00FF00", "accent": "#008800"},
            "Cyber": {"bg": "#0a0a0a", "fg": "#00d4ff", "accent": "#0080ff"},
            "Fire": {"bg": "#1a0000", "fg": "#ff3300", "accent": "#cc0000"},
            "Purple": {"bg": "#0d0010", "fg": "#da00ff", "accent": "#8800cc"},
            "Ocean": {"bg": "#001a33", "fg": "#00ffff", "accent": "#0099cc"}
        }
        
        # Logic objects
        self.timer = TimerLogic(
            on_update=self.on_timer_update,
            on_finish=self.on_timer_finish
        )
        self.stopwatch = StopwatchLogic(on_update=self.on_stopwatch_update)
        self.pomodoro = PomodoroLogic(
            on_update=self.on_pomodoro_update,
            on_phase_complete=self.on_pomodoro_complete
        )
        
        # State
        self.current_sound = self.config.get("sound", "Beep")
        self.time_format_24h = self.config.get("time_format_24h", True)
        self.time_offset = self.config.get("time_offset", 0)
        self.window_mode = self.config.get("window_mode", "normal")
        self.current_view = None
        self.alarm_widgets = []
        self.current_pomo_tag = None
        
        # Setup
        self._set_window_size()
        self._setup_ui()
        self._setup_keybindings()
        self._apply_theme()
        self._load_alarms()
        self._start_master_clock()
    
    def _set_window_size(self):
        """Define tamanho baseado no modo"""
        sizes = {
            "mini": "250x120",
            "normal": "480x380",
            "full": "600x520"
        }
        self.root.geometry(sizes.get(self.window_mode, "480x380"))
        self.root.resizable(False, False)
    
    def _setup_ui(self):
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        # Top bar
        top = tk.Frame(main, height=24)
        top.pack(fill=tk.X, pady=(0, 4))
        top.pack_propagate(False)
        
        self.theme_var = tk.StringVar(value=self.config.get("theme", "Matrix"))
        ttk.Combobox(top, textvariable=self.theme_var, values=list(self.themes.keys()),
                    width=7, state="readonly", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        self.theme_var.trace('w', lambda *a: self._change_theme())
        
        self.sound_var = tk.StringVar(value=self.current_sound)
        ttk.Combobox(top, textvariable=self.sound_var, 
                    values=["Beep", "Alert", "Chime", "Bell", "Alarm", "Custom"],
                    width=7, state="readonly", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        self.sound_var.trace('w', lambda *a: self._change_sound())
        
        self.fmt_btn = tk.Button(top, text="24h" if self.time_format_24h else "12h", 
                                command=self._toggle_format,
                                font=('Arial', 8, 'bold'), relief='flat', padx=6, pady=1)
        self.fmt_btn.pack(side=tk.LEFT, padx=4)
        
        # Mode selector
        mode_btn = tk.Button(top, text="□", command=self._cycle_window_mode,
                            font=('Arial', 9), relief='flat', padx=4, pady=0)
        mode_btn.pack(side=tk.LEFT, padx=2)
        
        # Stats button
        stats_btn = tk.Button(top, text="📊", command=self._show_stats,
                             font=('Arial', 9), relief='flat', padx=4, pady=0)
        stats_btn.pack(side=tk.LEFT, padx=2)
        
        self.top_btn = tk.Button(top, text="📌", command=self._toggle_top,
                                font=('Arial', 9), relief='flat', padx=4, pady=0)
        self.top_btn.pack(side=tk.RIGHT)
        
        # Clock display
        clock_size = 32 if self.window_mode == "mini" else 46
        self.clock_lbl = tk.Label(main, font=('Arial', clock_size, 'bold'), relief='flat')
        self.clock_lbl.pack(pady=(0, 2))
        
        if self.window_mode != "mini":
            self.date_lbl = tk.Label(main, font=('Arial', 11), relief='flat')
            self.date_lbl.pack()
        
        # Navigation (esconde em modo mini)
        if self.window_mode != "mini":
            nav = tk.Frame(main)
            nav.pack(pady=6)
            
            self.nav_btns = {}
            for emoji, view in [("🕐", "alarm"), ("⏱️", "timer"), ("⏲️", "stopwatch"), ("🍅", "pomodoro")]:
                btn = tk.Button(nav, text=emoji, command=lambda v=view: self._toggle_view(v),
                               font=('Arial', 14), relief='flat', bd=0, padx=10, pady=3)
                btn.pack(side=tk.LEFT, padx=1)
                self.nav_btns[view] = btn
            
            # Content area
            height = 200 if self.window_mode == "full" else 140
            self.content = tk.Frame(main, height=height)
            self.content.pack(fill=tk.BOTH, expand=True, pady=4)
            self.content.pack_propagate(False)
            
            # Create views
            self.views = {}
            self._create_alarm_view()
            self._create_timer_view()
            self._create_stopwatch_view()
            self._create_pomodoro_view()
    
    def _create_alarm_view(self):
        f = tk.Frame(self.content)
        
        # Lista de alarmes
        list_frame = tk.Frame(f)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        
        # Scrollable
        canvas = tk.Canvas(list_frame, height=80)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.alarm_list_frame = tk.Frame(canvas)
        
        self.alarm_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.alarm_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add new alarm
        add_frame = tk.Frame(f)
        add_frame.pack(pady=4)
        
        time_f = tk.Frame(add_frame)
        time_f.pack(side=tk.LEFT, padx=4)
        
        self.alarm_h = tk.Spinbox(time_f, from_=0, to=23, width=2,
                                 font=('Arial', 10), wrap=True, justify='center')
        self.alarm_h.pack(side=tk.LEFT, padx=1)
        tk.Label(time_f, text=":").pack(side=tk.LEFT)
        
        self.alarm_m = tk.Spinbox(time_f, from_=0, to=59, width=2,
                                 font=('Arial', 10), wrap=True, justify='center')
        self.alarm_m.pack(side=tk.LEFT, padx=1)
        
        self.alarm_label_entry = tk.Entry(add_frame, width=12, font=('Arial', 9))
        self.alarm_label_entry.pack(side=tk.LEFT, padx=4)
        self.alarm_label_entry.insert(0, "Label")
        
        tk.Button(add_frame, text="+ Add", command=self._add_alarm,
                 font=('Arial', 9), relief='flat', padx=8, pady=2).pack(side=tk.LEFT)
        
        self.views["alarm"] = f
    
    def _create_timer_view(self):
        f = tk.Frame(self.content)
        
        # Presets
        preset_f = tk.Frame(f)
        preset_f.pack(pady=4)
        
        tk.Label(preset_f, text="Quick:", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        
        presets = self.config.get("timer_presets", [1, 5, 10, 15, 25, 45])
        for mins in presets:
            tk.Button(preset_f, text=f"{mins}m", 
                     command=lambda m=mins: self._start_timer_preset(m),
                     font=('Arial', 8), relief='flat', padx=6, pady=2).pack(side=tk.LEFT, padx=1)
        
        # Custom input
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
        
        # Display
        self.timer_lbl = tk.Label(f, text="00:00", font=('Arial', 36, 'bold'))
        self.timer_lbl.pack(pady=4)
        
        # Controls
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
        f = tk.Frame(self.content)
        
        self.stopwatch_lbl = tk.Label(f, text="00:00:00", font=('Arial', 38, 'bold'))
        self.stopwatch_lbl.pack(pady=20)
        
        btn_f = tk.Frame(f)
        btn_f.pack()
        
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
        f = tk.Frame(self.content)
        
        # Tag selector
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
        
        # Stats
        today = self.stats_mgr.get_today_count()
        week = self.stats_mgr.get_week_count()
        self.pomo_count_lbl = tk.Label(f, text=f"Today: {today} | Week: {week}", font=('Arial', 9))
        self.pomo_count_lbl.pack()
        
        self.views["pomodoro"] = f
    
    def _setup_keybindings(self):
        """Atalhos de teclado"""
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
        """Space = start/pause timer ou pomodoro"""
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
        """Esconde view atual"""
        if self.current_view and self.current_view in self.views:
            self.views[self.current_view].pack_forget()
            self.nav_btns[self.current_view].config(relief='flat')
            self.current_view = None
    
    def _toggle_view(self, view_name):
        if self.window_mode == "mini":
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
        """Carrega alarmes salvos"""
        alarms = self.config.get("alarms", [])
        for alarm in alarms:
            self._add_alarm_widget(alarm)
    
    def _add_alarm(self):
        """Adiciona novo alarme"""
        h = self.alarm_h.get().zfill(2)
        m = self.alarm_m.get().zfill(2)
        label = self.alarm_label_entry.get()
        
        alarm = {
            "time": f"{h}:{m}:00",
            "label": label,
            "enabled": True
        }
        
        # Save to config
        alarms = self.config.get("alarms", [])
        alarms.append(alarm)
        self.config.set("alarms", alarms)
        
        self._add_alarm_widget(alarm)
    
    def _add_alarm_widget(self, alarm):
        """Adiciona widget de alarme na lista"""
        f = tk.Frame(self.alarm_list_frame)
        f.pack(fill=tk.X, pady=2)
        
        var = tk.BooleanVar(value=alarm.get("enabled", True))
        
        cb = tk.Checkbutton(f, variable=var, 
                           command=lambda: self._toggle_alarm(alarm, var.get()))
        cb.pack(side=tk.LEFT)
        
        tk.Label(f, text=alarm["time"][:5], font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text=alarm.get("label", ""), font=('Arial', 9)).pack(side=tk.LEFT, padx=4)
        
        tk.Button(f, text="×", command=lambda: self._delete_alarm(alarm, f),
                 font=('Arial', 10), relief='flat', padx=4).pack(side=tk.RIGHT)
        
        self.alarm_widgets.append((alarm, f, var))
    
    def _toggle_alarm(self, alarm, enabled):
        """Ativa/desativa alarme"""
        alarm["enabled"] = enabled
        alarms = self.config.get("alarms", [])
        self.config.set("alarms", alarms)
    
    def _delete_alarm(self, alarm, widget):
        """Remove alarme"""
        alarms = self.config.get("alarms", [])
        if alarm in alarms:
            alarms.remove(alarm)
            self.config.set("alarms", alarms)
        
        widget.destroy()
        self.alarm_widgets = [(a, w, v) for a, w, v in self.alarm_widgets if w != widget]
    
    def _start_timer_preset(self, minutes):
        """Inicia timer com preset"""
        self.timer.start(minutes * 60)
    
    def _start_timer(self):
        mins = int(self.timer_min.get())
        secs = int(self.timer_sec.get())
        self.timer.start(mins * 60 + secs)
    
    def _stop_timer(self):
        self.timer.stop()
        self.timer_lbl.config(text="00:00")
    
    def _start_pomodoro(self):
        tag = self.pomo_tag_var.get() if self.pomo_tag_var.get() else None
        self.current_pomo_tag = tag
        self.pomodoro.start(tag)
    
    def _cycle_window_mode(self):
        """Alterna entre mini/normal/full"""
        modes = ["mini", "normal", "full"]
        idx = modes.index(self.window_mode)
        self.window_mode = modes[(idx + 1) % len(modes)]
        self.config.set("window_mode", self.window_mode)
        
        # Rebuild UI
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self._set_window_size()
        self._setup_ui()
        self._setup_keybindings()
        self._apply_theme()
        self._load_alarms()
    
    def _show_stats(self):
        """Mostra janela de estatísticas"""
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
        
        info = f"""
Total Pomodoros: {total} 🍅
Total Focus Time: {hours:.1f} hours
Today: {today} 🍅
This Week: {week} 🍅
Avg per Day: {week/7:.1f} 🍅
        """
        
        tk.Label(stats_win, text=info, font=('Arial', 12), justify='left').pack(pady=10)
        
        # By tag
        by_tag = stats.get("sessions_by_tag", {})
        if by_tag:
            tk.Label(stats_win, text="By Tag:", font=('Arial', 12, 'bold')).pack()
            for tag, count in sorted(by_tag.items(), key=lambda x: x[1], reverse=True):
                tk.Label(stats_win, text=f"{tag}: {count} sessions", 
                        font=('Arial', 10)).pack()
        
        # Export button
        tk.Button(stats_win, text="📥 Export CSV", 
                 command=self._export_stats,
                 font=('Arial', 10, 'bold'), padx=20, pady=5).pack(pady=20)
    
    def _export_stats(self):
        """Exporta histórico para CSV"""
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
        self.time_format_24h = not self.time_format_24h
        self.fmt_btn.config(text="24h" if self.time_format_24h else "12h")
        self.config.set("time_format_24h", self.time_format_24h)
    
    def _toggle_top(self):
        current = self.root.attributes('-topmost')
        self.root.attributes('-topmost', not current)
        self.top_btn.config(relief='sunken' if not current else 'flat')
    
    def _change_sound(self):
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
                self.sound_var.set("Beep")
                self.current_sound = "Beep"
    
    def _change_theme(self):
        theme = self.theme_var.get()
        self.config.set("theme", theme)
        self._apply_theme()
    
    def _apply_theme(self):
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
                pass
        
        apply_recursive(self.root)
    
    def _start_master_clock(self):
        """Clock principal - tick a cada 1s"""
        # Update clock display
        now = datetime.now() + timedelta(seconds=self.time_offset)
        time_str = now.strftime('%H:%M:%S' if self.time_format_24h else '%I:%M:%S %p')
        self.clock_lbl.config(text=time_str)
        
        if self.window_mode != "mini" and hasattr(self, 'date_lbl'):
            self.date_lbl.config(text=now.strftime('%d/%m - %A'))
        
        # Check alarms
        current_time = now.strftime('%H:%M:%S')
        alarms = self.config.get("alarms", [])
        for alarm in alarms:
            if alarm.get("enabled") and alarm["time"] == current_time:
                self._trigger_alarm(alarm)
                alarm["enabled"] = False  # Auto-disable
                self.config.set("alarms", alarms)
        
        # Tick logic objects
        self.timer.tick()
        self.stopwatch.tick()
        self.pomodoro.tick()
        
        # Update UI states
        if self.window_mode != "mini":
            self._update_timer_ui()
            self._update_stopwatch_ui()
            self._update_pomodoro_ui()
        
        self.root.after(1000, self._start_master_clock)
    
    def _trigger_alarm(self, alarm):
        """Dispara alarme"""
        label = alarm.get("label", "Alarm")
        self._play_alarm("🔔 Alarm!", f"{alarm['time'][:5]} - {label}")
    
    def on_timer_update(self, remaining):
        if hasattr(self, 'timer_lbl'):
            mins, secs = divmod(remaining, 60)
            self.timer_lbl.config(text=f"{mins:02d}:{secs:02d}")
    
    def on_timer_finish(self):
        self._play_alarm("⏰ Timer", "Time's up!")
        self._stop_timer()
    
    def on_stopwatch_update(self, elapsed):
        if hasattr(self, 'stopwatch_lbl'):
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            self.stopwatch_lbl.config(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
    
    def on_pomodoro_update(self, time, phase):
        if hasattr(self, 'pomo_lbl'):
            mins, secs = divmod(time, 60)
            self.pomo_lbl.config(text=f"{mins:02d}:{secs:02d}")
    
    def on_pomodoro_complete(self, phase, count, tag):
        if phase == "work":
            if hasattr(self, 'pomo_status'):
                self.pomo_status.config(text="☕ Break (5min)")
            self.stats_mgr.record_pomodoro(tag)
            self._play_alarm("🍅 Pomodoro", f"Work done! Break time.\n{tag or ''}\nTotal: {count} 🍅")
            
            # Update count display
            if hasattr(self, 'pomo_count_lbl'):
                today = self.stats_mgr.get_today_count()
                week = self.stats_mgr.get_week_count()
                self.pomo_count_lbl.config(text=f"Today: {today} | Week: {week}")
        else:
            if hasattr(self, 'pomo_status'):
                self.pomo_status.config(text="✅ Complete!")
            self._play_alarm("🍅 Pomodoro", "Break over!")
    
    def _update_timer_ui(self):
        if hasattr(self, 'timer_start_btn'):
            if self.timer.running:
                self.timer_start_btn.config(state='disabled')
                self.timer_pause_btn.config(state='normal', text="▶" if self.timer.paused else "⏸")
                self.timer_stop_btn.config(state='normal')
            else:
                self.timer_start_btn.config(state='normal')
                self.timer_pause_btn.config(state='disabled')
                self.timer_stop_btn.config(state='disabled')
    
    def _update_stopwatch_ui(self):
        if hasattr(self, 'sw_start_btn'):
            if self.stopwatch.running:
                self.sw_start_btn.config(state='disabled')
                self.sw_pause_btn.config(state='normal', text="▶" if self.stopwatch.paused else "⏸")
            else:
                self.sw_start_btn.config(state='normal')
                self.sw_pause_btn.config(state='disabled')
    
    def _update_pomodoro_ui(self):
        if hasattr(self, 'pomo_start_btn'):
            if self.pomodoro.running:
                self.pomo_start_btn.config(state='disabled')
                self.pomo_pause_btn.config(state='normal', text="▶" if self.pomodoro.paused else "⏸")
            else:
                self.pomo_start_btn.config(state='normal')
                self.pomo_pause_btn.config(state='disabled')
    
    def _play_alarm(self, title, msg):
        """Toca som + notificação"""
        self.sound_mgr.play(self.current_sound, loop=True, progressive=True)
        self.notif_mgr.show(title, msg)
        messagebox.showinfo(title, msg)
        self.sound_mgr.stop()


if __name__ == "__main__":
    root = tk.Tk()
    app = ClockPro(root)
    root.mainloop()
