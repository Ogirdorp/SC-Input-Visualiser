import tkinter as tk
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time

# ============================================
# Windows Multimedia API
# ============================================

winmm = ctypes.WinDLL('winmm', use_last_error=True)

JOYERR_NOERROR = 0
JOY_RETURNALL = 0xFF

class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('dwXpos', wintypes.DWORD),
        ('dwYpos', wintypes.DWORD),
        ('dwZpos', wintypes.DWORD),
        ('dwRpos', wintypes.DWORD),
        ('dwUpos', wintypes.DWORD),
        ('dwVpos', wintypes.DWORD),
        ('dwButtons', wintypes.DWORD),
        ('dwButtonNumber', wintypes.DWORD),
        ('dwPOV', wintypes.DWORD),
        ('dwReserved1', wintypes.DWORD),
        ('dwReserved2', wintypes.DWORD),
    ]

joyGetNumDevs = winmm.joyGetNumDevs
joyGetNumDevs.restype = wintypes.UINT

joyGetPosEx = winmm.joyGetPosEx
joyGetPosEx.argtypes = [wintypes.UINT, ctypes.POINTER(JOYINFOEX)]
joyGetPosEx.restype = wintypes.UINT


def read_joystick(joy_id):
    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(JOYINFOEX)
    info.dwFlags = JOY_RETURNALL
    
    if joyGetPosEx(joy_id, ctypes.byref(info)) != JOYERR_NOERROR:
        return None
    
    def normalize(val):
        return ((val / 65535.0) * 2.0) - 1.0
    
    buttons = [i for i in range(32) if info.dwButtons & (1 << i)]
    
    return {
        'x': normalize(info.dwXpos),
        'y': normalize(info.dwYpos),
        'z': normalize(info.dwZpos),
        'r': normalize(info.dwRpos),
        'u': normalize(info.dwUpos),
        'v': normalize(info.dwVpos),
        'buttons': buttons,
    }


def find_connected_joysticks():
    return [i for i in range(joyGetNumDevs()) if read_joystick(i) is not None]


# ============================================
# Configuration
# ============================================

CONFIG_FILE = "overlay_config.json"

DEFAULT_CONFIG = {
    "stick_device": 3,
    "stick_x_axis": "x",
    "stick_y_axis": "y",
    "boost_button": 1,
    "pedals_device": 2,
    "throttle_axis": "z",
    "reverse_axis": "y",
    "window_x": 50,
    "window_y": 50,
    "hold_threshold": 5.0,  # seconds
    "axis_deadzone": 0.3,   # threshold to consider "holding"
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# ============================================
# Colors
# ============================================

BG_DARK = '#0d1b2a'
BG_PANEL = '#1b2838'
ACCENT = '#00ffc8'
ACCENT_DIM = '#00aa88'
TEXT_DIM = '#4a6572'
WARNING = '#ff6b6b'
BOOST_OFF = '#3d4f5f'
BOOST_ON = '#ff4444'
THROTTLE_COLOR = '#00ffc8'
REVERSE_COLOR = '#ff6b6b'


# ============================================
# Overlay Application
# ============================================

class JoystickOverlay:
    def __init__(self):
        self.config = load_config()
        self.running = True
        self.show_config = False
        
        # Hold detection state
        self.hold_start_x = None  # timestamp when started holding X
        self.hold_start_y = None  # timestamp when started holding Y
        self.hold_direction_x = None  # 'left' or 'right'
        self.hold_direction_y = None  # 'up' or 'down'
        
        # Print info
        print("=" * 50)
        print("HOSAM Joystick Overlay v2")
        print("=" * 50)
        connected = find_connected_joysticks()
        print(f"Detected joysticks: {connected if connected else 'None'}")
        print("Drag to move • Esc to quit")
        print("=" * 50)
        
        # Create window
        self.root = tk.Tk()
        self.root.title("HOSAM Overlay")
        self.root.geometry(f"560x220+{self.config['window_x']}+{self.config['window_y']}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.95)
        self.root.configure(bg=BG_DARK)
        
        self.root.bind('<Escape>', lambda e: self.quit())
        self.root.bind('<Button-1>', self.on_click)
        self.root.bind('<B1-Motion>', self.on_drag)
        
        self.drag_x = 0
        self.drag_y = 0
        
        self.create_ui()
        self.update_ui()
    
    def create_ui(self):
        # Main container
        self.main_frame = tk.Frame(self.root, bg=BG_DARK, padx=15, pady=12)
        self.main_frame.pack(fill='both', expand=True)
        
        # Top row - visualizations
        viz_frame = tk.Frame(self.main_frame, bg=BG_DARK)
        viz_frame.pack(fill='both', expand=True)
        
        # === STICK ===
        stick_frame = tk.Frame(viz_frame, bg=BG_DARK)
        stick_frame.pack(side='left', padx=(0, 20))
        
        # Stick canvas with grid
        self.stick_canvas = tk.Canvas(stick_frame, width=140, height=140, bg=BG_PANEL, 
                                       highlightthickness=2, highlightbackground=ACCENT_DIM)
        self.stick_canvas.pack()
        
        # Draw grid
        for i in range(1, 3):
            x = i * 46.67
            self.stick_canvas.create_line(x, 0, x, 140, fill='#2a3f4f', width=1)
            self.stick_canvas.create_line(0, x, 140, x, fill='#2a3f4f', width=1)
        
        # Center lines
        self.stick_canvas.create_line(70, 0, 70, 140, fill='#3a5a6f', width=1)
        self.stick_canvas.create_line(0, 70, 140, 70, fill='#3a5a6f', width=1)
        
        # Stick dot
        self.stick_dot = self.stick_canvas.create_oval(55, 55, 85, 85, fill=ACCENT, outline='')
        
        # Axis values
        self.axis_label = tk.Label(stick_frame, text="X: -0.00  Y: -0.00", font=('Consolas', 10), 
                                   fg=ACCENT, bg=BG_DARK)
        self.axis_label.pack(pady=(8, 0))
        
        # Hold warning
        self.hold_warning = tk.Label(stick_frame, text="", font=('Segoe UI', 10, 'bold'), 
                                     fg=WARNING, bg=BG_DARK)
        self.hold_warning.pack(pady=(8, 0))
        
        # === BOOST ===
        boost_frame = tk.Frame(viz_frame, bg=BG_DARK)
        boost_frame.pack(side='left', padx=20)
        
        self.boost_canvas = tk.Canvas(boost_frame, width=50, height=50, bg=BG_DARK, 
                                       highlightthickness=0)
        self.boost_canvas.pack()
        self.boost_indicator = self.boost_canvas.create_oval(2, 2, 48, 48, fill=BOOST_OFF, outline='#5a6a7a', width=2)
        self.boost_text = self.boost_canvas.create_text(25, 25, text=f"B{self.config['boost_button']}", 
                                                        fill='#8a9aa8', font=('Segoe UI', 11, 'bold'))
        
        tk.Label(boost_frame, text="BOOST", font=('Segoe UI', 9), fg=TEXT_DIM, bg=BG_DARK).pack(pady=(5, 0))
        
        # === PEDALS ===
        pedals_frame = tk.Frame(viz_frame, bg=BG_DARK)
        pedals_frame.pack(side='left', padx=20, fill='y')
        
        tk.Label(pedals_frame, text="PEDALS", font=('Segoe UI', 9), fg=ACCENT, bg=BG_DARK).pack(anchor='w')
        
        # Throttle
        t_frame = tk.Frame(pedals_frame, bg=BG_DARK)
        t_frame.pack(fill='x', pady=8)
        tk.Label(t_frame, text="T", font=('Segoe UI', 10, 'bold'), fg=TEXT_DIM, bg=BG_DARK, width=2).pack(side='left')
        
        self.throttle_canvas = tk.Canvas(t_frame, width=150, height=20, bg=BG_PANEL, 
                                          highlightthickness=0)
        self.throttle_canvas.pack(side='left', padx=8)
        self.throttle_bar = self.throttle_canvas.create_rectangle(0, 0, 0, 20, fill=THROTTLE_COLOR, outline='')
        
        self.throttle_label = tk.Label(t_frame, text="50%", font=('Consolas', 10), fg=ACCENT, bg=BG_DARK, width=4)
        self.throttle_label.pack(side='left')
        
        # Reverse
        r_frame = tk.Frame(pedals_frame, bg=BG_DARK)
        r_frame.pack(fill='x', pady=8)
        tk.Label(r_frame, text="R", font=('Segoe UI', 10, 'bold'), fg=TEXT_DIM, bg=BG_DARK, width=2).pack(side='left')
        
        self.reverse_canvas = tk.Canvas(r_frame, width=150, height=20, bg=BG_PANEL, 
                                         highlightthickness=0)
        self.reverse_canvas.pack(side='left', padx=8)
        self.reverse_bar = self.reverse_canvas.create_rectangle(0, 0, 0, 20, fill=REVERSE_COLOR, outline='')
        
        self.reverse_label = tk.Label(r_frame, text="50%", font=('Consolas', 10), fg=ACCENT, bg=BG_DARK, width=4)
        self.reverse_label.pack(side='left')
        
        # === CONFIG BUTTON (under pedals) ===
        self.config_btn = tk.Label(pedals_frame, text="⚙ Config", font=('Segoe UI', 9), fg=ACCENT, bg=BG_DARK, 
                                   cursor='hand2')
        self.config_btn.pack(anchor='e', pady=(5, 0))
        self.config_btn.bind('<Button-1>', lambda e: self.toggle_config())
    
    def toggle_config(self):
        self.show_config = not self.show_config
        if self.show_config:
            # Create popup window
            self.config_window = tk.Toplevel(self.root)
            self.config_window.title("Config")
            self.config_window.geometry("300x150")
            self.config_window.configure(bg=BG_PANEL)
            self.config_window.attributes('-topmost', True)
            self.config_window.resizable(False, False)
            
            # Position next to main window
            x = self.root.winfo_x() + self.root.winfo_width() + 10
            y = self.root.winfo_y()
            self.config_window.geometry(f"+{x}+{y}")
            
            # Config content
            frame = tk.Frame(self.config_window, bg=BG_PANEL, padx=15, pady=15)
            frame.pack(fill='both', expand=True)
            
            # Stick ID
            row1 = tk.Frame(frame, bg=BG_PANEL)
            row1.pack(fill='x', pady=5)
            tk.Label(row1, text="Stick ID:", font=('Segoe UI', 10), fg=TEXT_DIM, bg=BG_PANEL, width=10, anchor='e').pack(side='left')
            self.stick_var = tk.StringVar(value=str(self.config['stick_device']))
            tk.Spinbox(row1, from_=0, to=15, width=5, textvariable=self.stick_var, 
                       command=self.on_config_change, font=('Consolas', 10)).pack(side='left', padx=10)
            
            # Pedals ID
            row2 = tk.Frame(frame, bg=BG_PANEL)
            row2.pack(fill='x', pady=5)
            tk.Label(row2, text="Pedals ID:", font=('Segoe UI', 10), fg=TEXT_DIM, bg=BG_PANEL, width=10, anchor='e').pack(side='left')
            self.pedals_var = tk.StringVar(value=str(self.config['pedals_device']))
            tk.Spinbox(row2, from_=0, to=15, width=5, textvariable=self.pedals_var, 
                       command=self.on_config_change, font=('Consolas', 10)).pack(side='left', padx=10)
            
            # Boost Button
            row3 = tk.Frame(frame, bg=BG_PANEL)
            row3.pack(fill='x', pady=5)
            tk.Label(row3, text="Boost Btn:", font=('Segoe UI', 10), fg=TEXT_DIM, bg=BG_PANEL, width=10, anchor='e').pack(side='left')
            self.btn_var = tk.StringVar(value=str(self.config['boost_button']))
            tk.Spinbox(row3, from_=0, to=31, width=5, textvariable=self.btn_var, 
                       command=self.on_config_change, font=('Consolas', 10)).pack(side='left', padx=10)
            
            self.config_btn.config(fg=WARNING)
            
            # Handle window close
            self.config_window.protocol("WM_DELETE_WINDOW", self.close_config)
        else:
            self.close_config()
    
    def close_config(self):
        if hasattr(self, 'config_window') and self.config_window:
            self.config_window.destroy()
            self.config_window = None
        self.show_config = False
        self.config_btn.config(fg=ACCENT)
    
    def on_config_change(self):
        try:
            if hasattr(self, 'stick_var'):
                self.config['stick_device'] = int(self.stick_var.get())
            if hasattr(self, 'pedals_var'):
                self.config['pedals_device'] = int(self.pedals_var.get())
            if hasattr(self, 'btn_var'):
                self.config['boost_button'] = int(self.btn_var.get())
                self.boost_canvas.itemconfig(self.boost_text, text=f"B{self.config['boost_button']}")
            save_config(self.config)
        except ValueError:
            pass
    
    def on_click(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
    
    def on_drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")
    
    def check_hold_time(self, stick_x, stick_y):
        """Check if player is holding a direction too long"""
        now = time.time()
        deadzone = self.config['axis_deadzone']
        threshold = self.config['hold_threshold']
        warnings = []
        
        # Check X axis
        if stick_x < -deadzone:
            direction = 'LEFT STRAFE'
            if self.hold_direction_x != 'left':
                self.hold_start_x = now
                self.hold_direction_x = 'left'
            elif now - self.hold_start_x > threshold:
                warnings.append(f"HOLDING {direction} TOO LONG")
        elif stick_x > deadzone:
            direction = 'RIGHT STRAFE'
            if self.hold_direction_x != 'right':
                self.hold_start_x = now
                self.hold_direction_x = 'right'
            elif now - self.hold_start_x > threshold:
                warnings.append(f"HOLDING {direction} TOO LONG")
        else:
            self.hold_start_x = None
            self.hold_direction_x = None
        
        # Check Y axis
        if stick_y < -deadzone:
            direction = 'FORWARD'
            if self.hold_direction_y != 'up':
                self.hold_start_y = now
                self.hold_direction_y = 'up'
            elif now - self.hold_start_y > threshold:
                warnings.append(f"HOLDING {direction} TOO LONG")
        elif stick_y > deadzone:
            direction = 'BACKWARD'
            if self.hold_direction_y != 'down':
                self.hold_start_y = now
                self.hold_direction_y = 'down'
            elif now - self.hold_start_y > threshold:
                warnings.append(f"HOLDING {direction} TOO LONG")
        else:
            self.hold_start_y = None
            self.hold_direction_y = None
        
        return warnings
    
    def update_ui(self):
        if not self.running:
            return
        
        try:
            stick_x, stick_y = 0.0, 0.0
            boost_pressed = False
            throttle_pct, reverse_pct = 50, 50
            
            # Read stick
            data = read_joystick(self.config['stick_device'])
            if data:
                stick_x = data.get(self.config['stick_x_axis'], 0.0)
                stick_y = data.get(self.config['stick_y_axis'], 0.0)
                boost_pressed = self.config['boost_button'] in data['buttons']
            
            # Read pedals
            data = read_joystick(self.config['pedals_device'])
            if data:
                raw_t = data.get(self.config['throttle_axis'], 0.0)
                raw_r = data.get(self.config['reverse_axis'], 0.0)
                throttle_pct = int(((raw_t + 1) / 2) * 100)
                reverse_pct = int(((raw_r + 1) / 2) * 100)
            
            # Update stick
            dot_x = 70 + (stick_x * 55)
            dot_y = 70 + (stick_y * 55)
            self.stick_canvas.coords(self.stick_dot, dot_x-15, dot_y-15, dot_x+15, dot_y+15)
            self.axis_label.config(text=f"X: {stick_x:+.2f}  Y: {stick_y:+.2f}")
            
            # Check hold warnings
            warnings = self.check_hold_time(stick_x, stick_y)
            if warnings:
                self.hold_warning.config(text=warnings[0])
            else:
                self.hold_warning.config(text="")
            
            # Update boost
            if boost_pressed:
                self.boost_canvas.itemconfig(self.boost_indicator, fill=BOOST_ON, outline=WARNING)
                self.boost_canvas.itemconfig(self.boost_text, fill='#ffffff')
            else:
                self.boost_canvas.itemconfig(self.boost_indicator, fill=BOOST_OFF, outline='#5a6a7a')
                self.boost_canvas.itemconfig(self.boost_text, fill='#8a9aa8')
            
            # Update pedals
            self.throttle_canvas.coords(self.throttle_bar, 0, 0, throttle_pct * 1.5, 20)
            self.throttle_label.config(text=f"{throttle_pct}%")
            
            self.reverse_canvas.coords(self.reverse_bar, 0, 0, reverse_pct * 1.5, 20)
            self.reverse_label.config(text=f"{reverse_pct}%")
            
        except Exception as e:
            print(f"Error: {e}")
        
        self.root.after(16, self.update_ui)
    
    def quit(self):
        self.running = False
        if hasattr(self, 'config_window') and self.config_window:
            self.config_window.destroy()
        self.config['window_x'] = self.root.winfo_x()
        self.config['window_y'] = self.root.winfo_y()
        save_config(self.config)
        self.root.destroy()
        sys.exit(0)
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = JoystickOverlay()
    app.run()
