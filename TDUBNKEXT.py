import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ctypes
import json
import os
import threading
import time
from datetime import datetime


# ============================================================
# TDU2 BNK AUTO UNPACKER
# ============================================================
#
# IMPORTANT:
#
# Mini BNK Manager is NOT searched for.
# Mini BNK Manager is NOT started by this application.
#
# The user must open Mini BNK Manager manually before starting
# an extraction.
#
# The application controls Mini BNK Manager using the calibrated
# mouse positions.
#
# Features:
#
# - Manual BNK folder selection
# - Manual output folder selection
# - Automatic output path entry
# - Original folder structure preservation
# - Individual folder for every BNK
# - Five-position mouse calibration
# - F5 Start
# - F6 Stop
# - F7 Test Positions
# - F8 Verify Extraction
# - F9 Configure Positions
# - F12 Save Calibration Position
# - Missing-file retry
# - Light / Dark theme
# - Safe / Fast / Turbo speed
# - Log file
# - Verification report
#
# ============================================================


# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CONFIG_FILE = os.path.join(
    BASE_DIR,
    "tdu2_bnk_config.json"
)

LOG_FILE = os.path.join(
    BASE_DIR,
    "tdu2_bnk_log.txt"
)

VERIFICATION_FILE = os.path.join(
    BASE_DIR,
    "tdu2_bnk_verification.txt"
)

PRESERVE_FOLDER_STRUCTURE = True

CREATE_BNK_SUBFOLDER = True


# ============================================================
# WINDOWS VIRTUAL KEYS
# ============================================================

VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F12 = 0x7B

VK_CONTROL = 0x11
VK_A = 0x41
VK_V = 0x56


# ============================================================
# WINDOWS MOUSE EVENTS
# ============================================================

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


# ============================================================
# SPEED PROFILES
# ============================================================

SPEEDS = {
    "Safe": {
        "mouse": 0.25,
        "click": 0.08,
        "paste": 0.50,
        "load": 2.50,
        "unpack": 2.00,
        "ok": 1.50
    },

    "Fast": {
        "mouse": 0.10,
        "click": 0.05,
        "paste": 0.20,
        "load": 1.20,
        "unpack": 1.00,
        "ok": 0.50
    },

    "Turbo": {
        "mouse": 0.01,
        "click": 0.01,
        "paste": 0.01,
        "load": 0.01,
        "unpack": 0.01,
        "ok": 0.01
    }
}


# ============================================================
# THEMES
# ============================================================

THEMES = {
    "Light": {
        "bg": "#F0F0F0",
        "fg": "#111111",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#111111",
        "list_bg": "#FFFFFF",
        "list_fg": "#111111",
        "button_bg": "#E6E6E6",
        "button_fg": "#111111",
        "select_bg": "#4A90E2",
        "select_fg": "#FFFFFF",
        "border": "#B8B8B8",
        "disabled_bg": "#D8D8D8",
        "disabled_fg": "#777777",
        "success": "#2E8B57",
        "warning": "#CC8400",
        "error": "#CC3333"
    },

    "Dark": {
        "bg": "#202124",
        "fg": "#F1F3F4",
        "entry_bg": "#303134",
        "entry_fg": "#FFFFFF",
        "list_bg": "#303134",
        "list_fg": "#FFFFFF",
        "button_bg": "#3C4043",
        "button_fg": "#FFFFFF",
        "select_bg": "#5F8DD3",
        "select_fg": "#FFFFFF",
        "border": "#5F6368",
        "disabled_bg": "#303134",
        "disabled_fg": "#777777",
        "success": "#4CAF80",
        "warning": "#E0A840",
        "error": "#FF6666"
    }
}


# ============================================================
# WINDOWS API
# ============================================================

if os.name != "nt":
    raise RuntimeError(
        "This application requires Windows."
    )


user32 = ctypes.windll.user32


class POINT(ctypes.Structure):

    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long)
    ]


def get_mouse_position():

    point = POINT()

    user32.GetCursorPos(
        ctypes.byref(point)
    )

    return (
        point.x,
        point.y
    )


def move_mouse(x, y):

    user32.SetCursorPos(
        int(x),
        int(y)
    )


def mouse_click(
    x,
    y,
    speed
):

    move_mouse(
        x,
        y
    )

    time.sleep(
        speed["mouse"]
    )

    user32.mouse_event(
        MOUSEEVENTF_LEFTDOWN,
        0,
        0,
        0,
        0
    )

    time.sleep(
        speed["click"]
    )

    user32.mouse_event(
        MOUSEEVENTF_LEFTUP,
        0,
        0,
        0,
        0
    )


def key_down(key):

    user32.keybd_event(
        key,
        0,
        0,
        0
    )


def key_up(key):

    user32.keybd_event(
        key,
        0,
        2,
        0
    )


def press_key(key):

    key_down(key)

    time.sleep(
        0.03
    )

    key_up(key)


def hotkey(
    key1,
    key2
):

    key_down(key1)

    time.sleep(
        0.03
    )

    key_down(key2)

    time.sleep(
        0.03
    )

    key_up(key2)

    time.sleep(
        0.03
    )

    key_up(key1)


def key_pressed(vk_code):

    return bool(
        user32.GetAsyncKeyState(
            vk_code
        ) & 0x8000
    )


# ============================================================
# CONFIGURATION MANAGER
# ============================================================

class ConfigManager:

    def __init__(self):

        self.data = {
            "bnk_folder": "",
            "output_folder": "",
            "path_field": None,
            "output_field": None,
            "load": None,
            "unpack_all": None,
            "ok": None,
            "theme": "Light"
        }

        self.load()


    def load(self):

        if not os.path.isfile(
            CONFIG_FILE
        ):
            return

        try:

            with open(
                CONFIG_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                saved = json.load(
                    file
                )

            if not isinstance(
                saved,
                dict
            ):
                return

            for key in self.data:

                if key in saved:
                    self.data[key] = saved[key]

        except Exception as error:

            print(
                "Configuration error:",
                error
            )


    def save(self):

        try:

            with open(
                CONFIG_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    self.data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            return True

        except Exception as error:

            print(
                "Configuration save error:",
                error
            )

            return False


    def calibrated(self):

        required = [
            "path_field",
            "output_field",
            "load",
            "unpack_all",
            "ok"
        ]

        return all(
            self.data.get(key) is not None
            for key in required
        )


# ============================================================
# LOG MANAGER
# ============================================================

class LogManager:

    def __init__(self):

        self.lock = threading.Lock()


    def write(self, text):

        timestamp = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )

        line = (
            f"[{timestamp}] {text}\n"
        )

        try:

            with self.lock:

                with open(
                    LOG_FILE,
                    "a",
                    encoding="utf-8"
                ) as file:

                    file.write(
                        line
                    )

        except Exception as error:

            print(
                "Log error:",
                error
            )


    def start_session(self, total):

        try:

            with self.lock:

                with open(
                    LOG_FILE,
                    "a",
                    encoding="utf-8"
                ) as file:

                    file.write("\n")
                    file.write("=" * 70)
                    file.write("\n")
                    file.write(
                        "TDU2 BNK AUTO UNPACKER\n"
                    )
                    file.write(
                        "NEW EXTRACTION SESSION\n"
                    )
                    file.write(
                        f"BNK files: {total}\n"
                    )
                    file.write(
                        "Date: "
                        + datetime.now().strftime(
                            "%d/%m/%Y %H:%M:%S"
                        )
                        + "\n"
                    )
                    file.write("=" * 70)
                    file.write("\n")

        except Exception as error:

            print(
                "Log error:",
                error
            )


    def finish_session(
        self,
        total,
        completed,
        errors,
        interrupted
    ):

        self.write(
            "SESSION SUMMARY"
        )

        self.write(
            f"Total BNK files: {total}"
        )

        self.write(
            f"Completed: {completed}"
        )

        self.write(
            f"Errors: {errors}"
        )

        self.write(
            "Interrupted: "
            + (
                "YES"
                if interrupted
                else "NO"
            )
        )

        self.write(
            "=" * 70
        )


# ============================================================
# GLOBAL HOTKEY MANAGER
# ============================================================

class GlobalHotkeyManager:

    def __init__(
        self,
        application
    ):

        self.application = application
        self.running = True

        self.last_state = {
            VK_F5: False,
            VK_F6: False,
            VK_F7: False,
            VK_F8: False,
            VK_F9: False
        }

        self.thread = threading.Thread(
            target=self.worker,
            daemon=True
        )

        self.thread.start()


    def worker(self):

        while self.running:

            try:

                self.check_key(
                    VK_F5,
                    self.application.start_extraction
                )

                self.check_key(
                    VK_F6,
                    self.application.stop_extraction
                )

                self.check_key(
                    VK_F7,
                    self.application.test_positions
                )

                self.check_key(
                    VK_F8,
                    self.application.verify_extraction
                )

                self.check_key(
                    VK_F9,
                    self.application.open_calibration
                )

                time.sleep(
                    0.05
                )

            except Exception as error:

                print(
                    "Hotkey error:",
                    error
                )


    def check_key(
        self,
        vk_code,
        callback
    ):

        current = key_pressed(
            vk_code
        )

        previous = self.last_state[
            vk_code
        ]

        if current and not previous:

            try:

                self.application.root.after(
                    0,
                    callback
                )

            except Exception:
                pass

        self.last_state[
            vk_code
        ] = current


    def stop(self):

        self.running = False


# ============================================================
# CALIBRATION WINDOW
# ============================================================

class CalibrationWindow:

    def __init__(
        self,
        parent,
        config,
        callback,
        theme
    ):

        self.parent = parent
        self.config = config
        self.callback = callback
        self.theme = theme

        self.running = True
        self.step = 0
        self.last_f12_state = False

        self.steps = [
            (
                "PATH FIELD",
                "the field where the BNK path must be entered"
            ),
            (
                "OUTPUT FOLDER FIELD",
                "the field where the output folder path must be entered"
            ),
            (
                "LOAD",
                "the LOAD button"
            ),
            (
                "UNPACK ALL",
                "the UNPACK ALL button"
            ),
            (
                "OK",
                "the OK button"
            )
        ]

        self.window = tk.Toplevel(
            parent
        )

        self.window.title(
            "Configure Positions"
        )

        self.window.geometry(
            "680x520"
        )

        self.window.resizable(
            False,
            False
        )

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.create_interface()
        self.apply_theme()
        self.update_instruction()
        self.update_mouse()

        self.f12_thread = threading.Thread(
            target=self.f12_worker,
            daemon=True
        )

        self.f12_thread.start()


    def create_interface(self):

        self.title_label = tk.Label(
            self.window,
            text="POSITION CONFIGURATION",
            font=("Arial", 18, "bold")
        )

        self.title_label.pack(
            pady=15
        )

        self.step_label = tk.Label(
            self.window,
            text="",
            font=("Arial", 11, "bold")
        )

        self.step_label.pack()

        self.instruction = tk.Label(
            self.window,
            text="",
            font=("Arial", 11),
            justify="center"
        )

        self.instruction.pack(
            pady=18
        )

        self.position_frame = tk.LabelFrame(
            self.window,
            text="CURRENT MOUSE POSITION",
            padx=20,
            pady=15
        )

        self.position_frame.pack(
            padx=50,
            fill="x"
        )

        self.position_label = tk.Label(
            self.position_frame,
            text="X: 0    Y: 0",
            font=("Courier New", 22, "bold")
        )

        self.position_label.pack(
            pady=10
        )

        self.status_label = tk.Label(
            self.window,
            text="Waiting for F12...",
            font=("Arial", 10)
        )

        self.status_label.pack(
            pady=15
        )

        self.help_label = tk.Label(
            self.window,
            text=(
                "Move the mouse over the required control "
                "and press F12."
            ),
            font=("Arial", 11, "bold")
        )

        self.help_label.pack(
            pady=5
        )

        self.cancel_button = tk.Button(
            self.window,
            text="CANCEL",
            width=15,
            command=self.close
        )

        self.cancel_button.pack(
            pady=15
        )


    def apply_theme(self):

        colors = THEMES[
            self.theme
        ]

        self.window.configure(
            bg=colors["bg"]
        )

        widgets = [
            self.title_label,
            self.step_label,
            self.instruction,
            self.position_frame,
            self.position_label,
            self.status_label,
            self.help_label
        ]

        for widget in widgets:

            try:

                widget.configure(
                    bg=colors["bg"],
                    fg=colors["fg"]
                )

            except Exception:
                pass

        self.cancel_button.configure(
            bg=colors["button_bg"],
            fg=colors["button_fg"],
            activebackground=colors["select_bg"],
            activeforeground=colors["select_fg"]
        )


    def update_instruction(self):

        if not self.running:
            return

        name, description = self.steps[
            self.step
        ]

        self.step_label.config(
            text=(
                f"{self.step + 1} / "
                f"{len(self.steps)}    "
                f"{name}"
            )
        )

        self.instruction.config(
            text=(
                f"Move the cursor over {description}.\n\n"
                "Do not click.\n"
                "Press F12 to save this position."
            )
        )


    def update_mouse(self):

        if not self.running:
            return

        try:

            x, y = get_mouse_position()

            self.position_label.config(
                text=f"X: {x}    Y: {y}"
            )

            self.window.after(
                50,
                self.update_mouse
            )

        except Exception:
            pass


    def f12_worker(self):

        while self.running:

            try:

                current = key_pressed(
                    VK_F12
                )

                if current and not self.last_f12_state:

                    x, y = get_mouse_position()

                    self.parent.after(
                        0,
                        lambda x=x, y=y:
                        self.save_position(
                            x,
                            y
                        )
                    )

                self.last_f12_state = current

                time.sleep(
                    0.03
                )

            except Exception:

                time.sleep(
                    0.10
                )


    def save_position(
        self,
        x,
        y
    ):

        if not self.running:
            return

        name = self.steps[
            self.step
        ][0]

        position = [
            int(x),
            int(y)
        ]

        if name == "PATH FIELD":

            self.config.data[
                "path_field"
            ] = position

        elif name == "OUTPUT FOLDER FIELD":

            self.config.data[
                "output_field"
            ] = position

        elif name == "LOAD":

            self.config.data[
                "load"
            ] = position

        elif name == "UNPACK ALL":

            self.config.data[
                "unpack_all"
            ] = position

        elif name == "OK":

            self.config.data[
                "ok"
            ] = position

        self.config.save()

        colors = THEMES[
            self.theme
        ]

        self.status_label.config(
            text=(
                f"{name} saved: "
                f"X={x} Y={y}"
            ),
            fg=colors["success"]
        )

        self.step += 1

        if self.step >= len(
            self.steps
        ):

            messagebox.showinfo(
                "Configuration Complete",
                "All five positions have been saved."
            )

            self.close()
            return

        self.update_instruction()


    def close(self):

        if not self.running:
            return

        self.running = False

        try:
            self.window.destroy()
        except Exception:
            pass

        if self.callback:

            try:
                self.callback()
            except Exception:
                pass


# ============================================================
# MAIN APPLICATION
# ============================================================

class Application:

    def __init__(
        self,
        root
    ):

        self.root = root

        self.root.title(
            "TDU2 BNK Auto Unpacker"
        )

        self.root.geometry(
            "920x940"
        )

        self.root.resizable(
            False,
            False
        )

        self.config = ConfigManager()
        self.log = LogManager()

        self.stop_requested = False
        self.extraction_running = False
        self.verification_running = False

        self.current_files = []

        self.completed_files = set()
        self.error_files = set()

        self.calibration_window = None

        self.widget_registry = []

        self.create_interface()

        theme = self.config.data.get(
            "theme",
            "Light"
        )

        self.theme_variable.set(
            theme
        )

        self.apply_theme(
            theme
        )

        self.refresh_bnk_list()

        self.hotkeys = GlobalHotkeyManager(
            self
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )


    # ========================================================
    # INTERFACE
    # ========================================================

    def create_interface(self):

        self.title_label = tk.Label(
            self.root,
            text="TDU2 BNK AUTO UNPACKER",
            font=("Arial", 20, "bold")
        )

        self.title_label.pack(
            pady=15
        )

        # ----------------------------------------------------
        # BNK FOLDER
        # ----------------------------------------------------

        self.create_path_row(
            "BNK Folder:",
            "bnk_folder",
            self.select_bnk_folder
        )

        # ----------------------------------------------------
        # OUTPUT FOLDER
        # ----------------------------------------------------

        self.create_path_row(
            "Output Folder:",
            "output_folder",
            self.select_output_folder
        )

        # ----------------------------------------------------
        # OUTPUT INFORMATION
        # ----------------------------------------------------

        self.output_frame = tk.LabelFrame(
            self.root,
            text="Extraction Configuration",
            padx=15,
            pady=10
        )

        self.output_frame.pack(
            padx=30,
            pady=8,
            fill="x"
        )

        self.output_label = tk.Label(
            self.output_frame,
            anchor="w",
            justify="left"
        )

        self.output_label.pack(
            fill="x"
        )

        self.structure_label = tk.Label(
            self.output_frame,
            text=(
                "Folder structure: Preserved\n"
                "BNK subfolder: Enabled\n"
                "Output path: Selected by user"
            ),
            anchor="w",
            justify="left"
        )

        self.structure_label.pack(
            fill="x",
            pady=5
        )

        # ----------------------------------------------------
        # WARNING
        # ----------------------------------------------------

        self.manager_info_label = tk.Label(
            self.root,
            text=(
                "IMPORTANT: Open Mini BNK Manager manually "
                "before starting extraction."
            ),
            font=("Arial", 10, "bold")
        )

        self.manager_info_label.pack(
            pady=8
        )

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        self.settings_frame = tk.Frame(
            self.root
        )

        self.settings_frame.pack(
            pady=8
        )

        self.speed_text_label = tk.Label(
            self.settings_frame,
            text="Speed:"
        )

        self.speed_text_label.pack(
            side="left",
            padx=5
        )

        self.speed_variable = tk.StringVar(
            value="Fast"
        )

        self.speed_combo = ttk.Combobox(
            self.settings_frame,
            textvariable=self.speed_variable,
            values=[
                "Safe",
                "Fast",
                "Turbo"
            ],
            state="readonly",
            width=12
        )

        self.speed_combo.pack(
            side="left",
            padx=5
        )

        self.theme_text_label = tk.Label(
            self.settings_frame,
            text="Theme:"
        )

        self.theme_text_label.pack(
            side="left",
            padx=(25, 5)
        )

        self.theme_variable = tk.StringVar(
            value=self.config.data.get(
                "theme",
                "Light"
            )
        )

        self.theme_combo = ttk.Combobox(
            self.settings_frame,
            textvariable=self.theme_variable,
            values=[
                "Light",
                "Dark"
            ],
            state="readonly",
            width=12
        )

        self.theme_combo.pack(
            side="left"
        )

        self.theme_combo.bind(
            "<<ComboboxSelected>>",
            self.theme_changed
        )

        # ----------------------------------------------------
        # SEPARATOR
        # ----------------------------------------------------

        self.separator = tk.Frame(
            self.root,
            height=2
        )

        self.separator.pack(
            fill="x",
            padx=30,
            pady=8
        )

        # ----------------------------------------------------
        # CALIBRATION
        # ----------------------------------------------------

        self.calibration_button = tk.Button(
            self.root,
            text="CONFIGURE POSITIONS",
            width=30,
            height=2,
            font=("Arial", 10, "bold"),
            command=self.open_calibration
        )

        self.calibration_button.pack(
            pady=5
        )

        self.calibration_label = tk.Label(
            self.root,
            text=""
        )

        self.calibration_label.pack(
            pady=5
        )

        # ----------------------------------------------------
        # HOTKEYS
        # ----------------------------------------------------

        self.hotkey_frame = tk.LabelFrame(
            self.root,
            text="Keyboard Shortcuts",
            padx=10,
            pady=8
        )

        self.hotkey_frame.pack(
            padx=40,
            pady=8,
            fill="x"
        )

        self.hotkey_label = tk.Label(
            self.hotkey_frame,
            text=(
                "F5  = Start Extraction     "
                "F6  = Stop\n"
                "F7  = Test Positions       "
                "F8  = Verify Extraction\n"
                "F9  = Configure Positions  "
                "F12 = Save Calibration Position"
            ),
            font=("Consolas", 10),
            justify="center"
        )

        self.hotkey_label.pack()

        # ----------------------------------------------------
        # BNK LIST
        # ----------------------------------------------------

        self.bnk_title_label = tk.Label(
            self.root,
            text="BNK FILES FOUND",
            font=("Arial", 11, "bold")
        )

        self.bnk_title_label.pack(
            pady=5
        )

        list_frame = tk.Frame(
            self.root
        )

        list_frame.pack(
            padx=40
        )

        self.bnk_list = tk.Listbox(
            list_frame,
            width=100,
            height=10
        )

        self.bnk_list.pack(
            side="left"
        )

        self.scrollbar = tk.Scrollbar(
            list_frame,
            command=self.bnk_list.yview
        )

        self.scrollbar.pack(
            side="right",
            fill="y"
        )

        self.bnk_list.config(
            yscrollcommand=self.scrollbar.set
        )

        self.count_label = tk.Label(
            self.root,
            text="BNK files found: 0"
        )

        self.count_label.pack(
            pady=5
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        self.button_frame = tk.Frame(
            self.root
        )

        self.button_frame.pack(
            pady=10
        )

        self.test_button = tk.Button(
            self.button_frame,
            text="TEST POSITIONS",
            width=18,
            height=2,
            command=self.test_positions
        )

        self.test_button.pack(
            side="left",
            padx=4
        )

        self.start_button = tk.Button(
            self.button_frame,
            text="START EXTRACTION",
            width=20,
            height=2,
            font=("Arial", 10, "bold"),
            command=self.start_extraction
        )

        self.start_button.pack(
            side="left",
            padx=4
        )

        self.stop_button = tk.Button(
            self.button_frame,
            text="STOP",
            width=12,
            height=2,
            state="disabled",
            command=self.stop_extraction
        )

        self.stop_button.pack(
            side="left",
            padx=4
        )

        self.verify_button = tk.Button(
            self.button_frame,
            text="VERIFY EXTRACTION",
            width=20,
            height=2,
            command=self.verify_extraction
        )

        self.verify_button.pack(
            side="left",
            padx=4
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = tk.Label(
            self.root,
            text="Status: Ready",
            anchor="w"
        )

        self.status_label.pack(
            fill="x",
            padx=40,
            pady=5
        )

        self.update_output_information()
        self.update_calibration_status()


    # ========================================================
    # PATH ROW
    # ========================================================

    def create_path_row(
        self,
        label,
        key,
        command
    ):

        frame = tk.Frame(
            self.root
        )

        frame.pack(
            fill="x",
            padx=30,
            pady=5
        )

        label_widget = tk.Label(
            frame,
            text=label,
            width=23,
            anchor="w"
        )

        label_widget.pack(
            side="left"
        )

        variable = tk.StringVar(
            value=self.config.data.get(
                key,
                ""
            )
        )

        setattr(
            self,
            key + "_variable",
            variable
        )

        entry = tk.Entry(
            frame,
            textvariable=variable
        )

        entry.pack(
            side="left",
            fill="x",
            expand=True
        )

        button = tk.Button(
            frame,
            text="BROWSE",
            command=command
        )

        button.pack(
            side="left",
            padx=5
        )

        self.widget_registry.extend(
            [
                frame,
                label_widget,
                entry,
                button
            ]
        )


    # ========================================================
    # SELECT BNK FOLDER
    # ========================================================

    def select_bnk_folder(self):

        path = filedialog.askdirectory(
            title="Select BNK Folder"
        )

        if not path:
            return

        path = os.path.abspath(
            path
        )

        self.config.data[
            "bnk_folder"
        ] = path

        self.bnk_folder_variable.set(
            path
        )

        self.config.save()

        self.refresh_bnk_list()
        self.update_output_information()


    # ========================================================
    # SELECT OUTPUT FOLDER
    # ========================================================

    def select_output_folder(self):

        path = filedialog.askdirectory(
            title="Select Output Folder"
        )

        if not path:
            return

        path = os.path.abspath(
            path
        )

        self.config.data[
            "output_folder"
        ] = path

        self.output_folder_variable.set(
            path
        )

        self.config.save()

        self.update_output_information()


    # ========================================================
    # GET OUTPUT ROOT
    # ========================================================

    def get_output_root(self):

        folder = self.config.data.get(
            "output_folder",
            ""
        )

        if not folder:
            return ""

        return os.path.abspath(
            os.path.expanduser(
                folder
            )
        )


    # ========================================================
    # OUTPUT INFORMATION
    # ========================================================

    def update_output_information(self):

        output_root = self.get_output_root()

        if output_root:

            text = (
                "Selected output folder:\n"
                + output_root
            )

        else:

            text = (
                "Selected output folder:\n"
                "No output folder selected."
            )

        self.output_label.config(
            text=text
        )


    # ========================================================
    # FIND BNK FILES
    # ========================================================

    def find_bnk_files(self):

        folder = self.config.data.get(
            "bnk_folder",
            ""
        )

        if not folder:
            return []

        if not os.path.isdir(
            folder
        ):
            return []

        result = []

        for current_folder, folders, files in os.walk(
            folder
        ):

            for filename in files:

                if filename.lower().endswith(
                    ".bnk"
                ):

                    result.append(
                        os.path.join(
                            current_folder,
                            filename
                        )
                    )

        result.sort(
            key=lambda path:
            os.path.relpath(
                path,
                folder
            ).lower()
        )

        return result


    # ========================================================
    # REFRESH BNK LIST
    # ========================================================

    def refresh_bnk_list(self):

        if not hasattr(
            self,
            "bnk_list"
        ):
            return

        self.bnk_list.delete(
            0,
            tk.END
        )

        files = self.find_bnk_files()

        self.current_files = files

        base = self.config.data.get(
            "bnk_folder",
            ""
        )

        if not base:

            self.count_label.config(
                text="BNK files found: 0"
            )

            return

        for path in files:

            relative = os.path.relpath(
                path,
                base
            )

            self.bnk_list.insert(
                tk.END,
                relative
            )

        self.count_label.config(
            text=(
                f"BNK files found: "
                f"{len(files)}"
            )
        )


    # ========================================================
    # OUTPUT FOLDER FOR ONE BNK
    # ========================================================

    def get_output_folder_for_bnk(
        self,
        bnk_file
    ):

        bnk_root = os.path.abspath(
            self.config.data[
                "bnk_folder"
            ]
        )

        output_root = self.get_output_root()

        if not output_root:

            raise RuntimeError(
                "No output folder has been selected."
            )

        relative = os.path.relpath(
            bnk_file,
            bnk_root
        )

        relative_dir = os.path.dirname(
            relative
        )

        filename = os.path.basename(
            relative
        )

        name_without_ext = os.path.splitext(
            filename
        )[0]

        if PRESERVE_FOLDER_STRUCTURE:

            destination = os.path.join(
                output_root,
                relative_dir
            )

        else:

            destination = output_root

        if CREATE_BNK_SUBFOLDER:

            destination = os.path.join(
                destination,
                name_without_ext
            )

        os.makedirs(
            destination,
            exist_ok=True
        )

        return os.path.abspath(
            destination
        )


    # ========================================================
    # EXPECTED OUTPUT FOLDER
    # ========================================================

    def get_expected_output_folder(
        self,
        bnk_file
    ):

        bnk_root = os.path.abspath(
            self.config.data[
                "bnk_folder"
            ]
        )

        output_root = self.get_output_root()

        if not output_root:
            return ""

        relative = os.path.relpath(
            bnk_file,
            bnk_root
        )

        relative_dir = os.path.dirname(
            relative
        )

        filename = os.path.basename(
            relative
        )

        name_without_ext = os.path.splitext(
            filename
        )[0]

        if PRESERVE_FOLDER_STRUCTURE:

            expected = os.path.join(
                output_root,
                relative_dir
            )

        else:

            expected = output_root

        if CREATE_BNK_SUBFOLDER:

            expected = os.path.join(
                expected,
                name_without_ext
            )

        return os.path.abspath(
            expected
        )


    # ========================================================
    # CALIBRATION STATUS
    # ========================================================

    def update_calibration_status(self):

        colors = THEMES[
            self.theme_variable.get()
        ]

        if self.config.calibrated():

            self.calibration_label.config(
                text="Calibration complete",
                fg=colors["success"]
            )

        else:

            self.calibration_label.config(
                text=(
                    "Calibration required "
                    "(5 positions)"
                ),
                fg=colors["warning"]
            )


    # ========================================================
    # OPEN CALIBRATION
    # ========================================================

    def open_calibration(self):

        if self.extraction_running:
            return

        if self.calibration_window is not None:

            try:

                if self.calibration_window.window.winfo_exists():

                    self.calibration_window.window.lift()
                    return

            except Exception:
                pass

        self.calibration_window = CalibrationWindow(
            self.root,
            self.config,
            self.update_calibration_status,
            self.theme_variable.get()
        )


    # ========================================================
    # TEST POSITIONS
    # ========================================================

    def test_positions(self):

        if self.extraction_running:
            return

        if not self.config.calibrated():

            messagebox.showwarning(
                "Calibration",
                "Complete the five-position calibration first."
            )

            return

        answer = messagebox.askyesno(
            "Test Positions",
            (
                "The mouse will move to the five calibrated "
                "positions.\n\n"
                "1. PATH FIELD\n"
                "2. OUTPUT FOLDER FIELD\n"
                "3. LOAD\n"
                "4. UNPACK ALL\n"
                "5. OK\n\n"
                "Continue?"
            )
        )

        if not answer:
            return

        threading.Thread(
            target=self.test_worker,
            daemon=True
        ).start()


    def test_worker(self):

        positions = [
            (
                "PATH FIELD",
                self.config.data["path_field"]
            ),
            (
                "OUTPUT FOLDER FIELD",
                self.config.data["output_field"]
            ),
            (
                "LOAD",
                self.config.data["load"]
            ),
            (
                "UNPACK ALL",
                self.config.data["unpack_all"]
            ),
            (
                "OK",
                self.config.data["ok"]
            )
        ]

        for name, position in positions:

            if self.stop_requested:
                return

            self.set_status(
                f"Testing {name}..."
            )

            move_mouse(
                position[0],
                position[1]
            )

            time.sleep(
                1
            )

        self.set_status(
            "Position test completed."
        )


    # ========================================================
    # START EXTRACTION
    # ========================================================

    def start_extraction(
        self,
        files=None,
        retry_mode=False
    ):

        if self.extraction_running:
            return

        if files is None:

            files = self.find_bnk_files()

        if not files:

            messagebox.showwarning(
                "BNK Files",
                "No .bnk files were found."
            )

            return

        bnk_folder = self.config.data.get(
            "bnk_folder",
            ""
        )

        if not bnk_folder:

            messagebox.showwarning(
                "BNK Folder",
                "Select the BNK folder first."
            )

            return

        output_root = self.get_output_root()

        if not output_root:

            messagebox.showwarning(
                "Output Folder",
                "Select the output folder first."
            )

            return

        if not self.config.calibrated():

            messagebox.showwarning(
                "Calibration",
                "Complete the five-position calibration first."
            )

            return

        speed_name = self.speed_variable.get()

        if speed_name not in SPEEDS:

            speed_name = "Fast"

        if retry_mode:

            title = "Retry Missing Files"

            message = (
                f"Missing BNK files to retry: {len(files)}\n\n"
                f"Output folder:\n{output_root}\n\n"
                "Only the missing files will be processed.\n\n"
                "Make sure Mini BNK Manager is open.\n\n"
                "Continue?"
            )

        else:

            title = "Start Extraction"

            message = (
                f"BNK files found: {len(files)}\n"
                f"Speed: {speed_name}\n\n"
                f"Output folder:\n{output_root}\n\n"
                "The original folder structure will be preserved.\n"
                "A separate folder will be created for each BNK.\n\n"
                "Mini BNK Manager must already be open.\n"
                "This program will NOT start it automatically.\n\n"
                "Continue?"
            )

        answer = messagebox.askyesno(
            title,
            message
        )

        if not answer:
            return

        try:

            os.makedirs(
                output_root,
                exist_ok=True
            )

        except Exception as error:

            messagebox.showerror(
                "Output Error",
                str(error)
            )

            return

        self.stop_requested = False
        self.completed_files = set()
        self.error_files = set()
        self.extraction_running = True

        self.set_buttons_running(
            True
        )

        threading.Thread(
            target=self.extraction_worker,
            args=(
                files,
                speed_name,
                retry_mode
            ),
            daemon=True
        ).start()


    # ========================================================
    # CLIPBOARD
    # ========================================================

    def set_clipboard_text(
        self,
        text
    ):

        try:

            self.root.clipboard_clear()

            self.root.clipboard_append(
                text
            )

            self.root.update()

            return True

        except Exception as error:

            self.log.write(
                f"Clipboard error: {error}"
            )

            return False


    # ========================================================
    # PASTE INTO FIELD
    # ========================================================

    def paste_into_field(
        self,
        position,
        text,
        speed
    ):

        if not self.set_clipboard_text(
            text
        ):

            return False

        time.sleep(
            speed["paste"]
        )

        mouse_click(
            position[0],
            position[1],
            speed
        )

        hotkey(
            VK_CONTROL,
            VK_A
        )

        time.sleep(
            0.05
        )

        hotkey(
            VK_CONTROL,
            VK_V
        )

        time.sleep(
            speed["paste"]
        )

        return True


    # ========================================================
    # EXTRACTION WORKER
    # ========================================================

    def extraction_worker(
        self,
        files,
        speed_name,
        retry_mode
    ):

        speed = SPEEDS[
            speed_name
        ]

        total = len(
            files
        )

        completed = 0
        errors = 0

        session_name = (
            "RETRY MISSING FILES"
            if retry_mode
            else "NORMAL EXTRACTION"
        )

        self.log.start_session(
            total
        )

        self.log.write(
            f"Mode: {session_name}"
        )

        self.log.write(
            "Mini BNK Manager is expected "
            "to be opened manually."
        )

        for index, bnk_file in enumerate(
            files,
            start=1
        ):

            if self.stop_requested:
                break

            relative = os.path.relpath(
                bnk_file,
                self.config.data[
                    "bnk_folder"
                ]
            )

            try:

                output_for_bnk = (
                    self.get_output_folder_for_bnk(
                        bnk_file
                    )
                )

                self.log.write(
                    f"START: {relative}"
                )

                self.log.write(
                    f"OUTPUT: {output_for_bnk}"
                )

                # ------------------------------------------------
                # BNK PATH
                # ------------------------------------------------

                self.set_status(
                    f"{index}/{total} - "
                    f"Entering BNK path - "
                    f"{relative}"
                )

                path_field = self.config.data[
                    "path_field"
                ]

                if not self.paste_into_field(
                    path_field,
                    os.path.normpath(
                        bnk_file
                    ),
                    speed
                ):

                    raise RuntimeError(
                        "Unable to enter BNK path."
                    )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # OUTPUT FOLDER
                # ------------------------------------------------

                self.set_status(
                    f"{index}/{total} - "
                    f"Entering output path - "
                    f"{relative}"
                )

                output_field = self.config.data[
                    "output_field"
                ]

                if not self.paste_into_field(
                    output_field,
                    os.path.normpath(
                        output_for_bnk
                    ),
                    speed
                ):

                    raise RuntimeError(
                        "Unable to enter output folder."
                    )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # LOAD
                # ------------------------------------------------

                self.set_status(
                    f"{index}/{total} - "
                    f"LOAD - {relative}"
                )

                load = self.config.data[
                    "load"
                ]

                mouse_click(
                    load[0],
                    load[1],
                    speed
                )

                time.sleep(
                    speed["load"]
                )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # UNPACK ALL
                # ------------------------------------------------

                self.set_status(
                    f"{index}/{total} - "
                    f"UNPACK ALL - {relative}"
                )

                unpack = self.config.data[
                    "unpack_all"
                ]

                mouse_click(
                    unpack[0],
                    unpack[1],
                    speed
                )

                time.sleep(
                    speed["unpack"]
                )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # OK
                # ------------------------------------------------

                self.set_status(
                    f"{index}/{total} - "
                    f"OK - {relative}"
                )

                ok = self.config.data[
                    "ok"
                ]

                mouse_click(
                    ok[0],
                    ok[1],
                    speed
                )

                time.sleep(
                    speed["ok"]
                )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # SUCCESS
                # ------------------------------------------------

                completed += 1

                normalized = os.path.normcase(
                    os.path.abspath(
                        bnk_file
                    )
                )

                self.completed_files.add(
                    normalized
                )

                self.log.write(
                    f"OK: {relative}"
                )

            except Exception as error:

                errors += 1

                normalized = os.path.normcase(
                    os.path.abspath(
                        bnk_file
                    )
                )

                self.error_files.add(
                    normalized
                )

                self.log.write(
                    f"ERROR: {relative}"
                )

                self.log.write(
                    f"Error details: {error}"
                )

        interrupted = self.stop_requested

        self.log.finish_session(
            total,
            completed,
            errors,
            interrupted
        )

        if interrupted:

            self.set_status(
                f"Extraction stopped - "
                f"{completed}/{total} completed."
            )

        else:

            self.set_status(
                f"Extraction finished - "
                f"{completed}/{total} processed, "
                f"{errors} errors."
            )

        self.finish_extraction()


    # ========================================================
    # STOP EXTRACTION
    # ========================================================

    def stop_extraction(self):

        if not self.extraction_running:
            return

        self.stop_requested = True

        self.log.write(
            "STOP requested by user."
        )

        self.set_status(
            "STOP requested..."
        )


    # ========================================================
    # VERIFY EXTRACTION
    # ========================================================

    def verify_extraction(
        self,
        automatic=False
    ):

        if self.extraction_running:
            return

        if self.verification_running:
            return

        files = self.find_bnk_files()

        if not files:

            messagebox.showwarning(
                "Verification",
                "No BNK files were found."
            )

            return

        output_root = self.get_output_root()

        if not output_root:

            messagebox.showwarning(
                "Verification",
                "Select the output folder first."
            )

            return

        self.verification_running = True

        self.set_status(
            "Verifying extraction..."
        )

        threading.Thread(
            target=self.verify_worker,
            args=(files, automatic),
            daemon=True
        ).start()


    def verify_worker(
        self,
        files,
        automatic
    ):

        total = len(
            files
        )

        found = []
        missing = []

        for bnk_file in files:

            if self.stop_requested:
                break

            relative = os.path.relpath(
                bnk_file,
                self.config.data[
                    "bnk_folder"
                ]
            )

            expected_folder = (
                self.get_expected_output_folder(
                    bnk_file
                )
            )

            if os.path.isdir(
                expected_folder
            ):

                try:

                    contents = os.listdir(
                        expected_folder
                    )

                except Exception:

                    contents = []

                if contents:

                    found.append(
                        relative
                    )

                else:

                    missing.append(
                        relative
                    )

            else:

                missing.append(
                    relative
                )

        self.save_verification_report(
            total,
            found,
            missing
        )

        self.root.after(
            0,
            lambda:
            self.show_verification_result(
                files,
                total,
                found,
                missing,
                automatic
            )
        )


    # ========================================================
    # SAVE VERIFICATION REPORT
    # ========================================================

    def save_verification_report(
        self,
        total,
        found,
        missing
    ):

        try:

            with open(
                VERIFICATION_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(
                    "TDU2 BNK AUTO UNPACKER\n"
                )

                file.write(
                    "EXTRACTION VERIFICATION REPORT\n"
                )

                file.write(
                    "Date: "
                    + datetime.now().strftime(
                        "%d/%m/%Y %H:%M:%S"
                    )
                    + "\n\n"
                )

                file.write(
                    "Output folder:\n"
                )

                file.write(
                    self.get_output_root()
                    + "\n\n"
                )

                file.write(
                    f"Total BNK files: {total}\n"
                )

                file.write(
                    f"Present: {len(found)}\n"
                )

                file.write(
                    f"Missing: {len(missing)}\n\n"
                )

                file.write(
                    "=" * 70
                    + "\n"
                )

                file.write(
                    "MISSING FILES:\n"
                )

                file.write(
                    "=" * 70
                    + "\n"
                )

                if missing:

                    for item in missing:

                        file.write(
                            item
                            + "\n"
                        )

                else:

                    file.write(
                        "No missing BNK files.\n"
                    )

        except Exception as error:

            self.log.write(
                "Verification report error: "
                + str(error)
            )


    # ========================================================
    # VERIFICATION RESULT
    # ========================================================

    def show_verification_result(
        self,
        files,
        total,
        found,
        missing,
        automatic
    ):

        self.verification_running = False

        if not missing:

            messagebox.showinfo(
                "Verification Complete",
                (
                    "EXTRACTION COMPLETE\n\n"
                    f"Total BNK files: {total}\n"
                    f"Present: {len(found)}\n"
                    "Missing: 0\n\n"
                    "All BNK files were found in the "
                    "expected output locations."
                )
            )

            self.set_status(
                f"Verification OK - "
                f"{total}/{total} BNK files present."
            )

            return

        # ----------------------------------------------------
        # MISSING FILES WINDOW
        # ----------------------------------------------------

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "Extraction Verification"
        )

        window.geometry(
            "760x600"
        )

        window.resizable(
            True,
            True
        )

        theme = self.theme_variable.get()

        colors = THEMES[
            theme
        ]

        window.configure(
            bg=colors["bg"]
        )

        title = tk.Label(
            window,
            text="EXTRACTION VERIFICATION",
            font=("Arial", 17, "bold"),
            bg=colors["bg"],
            fg=colors["fg"]
        )

        title.pack(
            pady=12
        )

        summary = tk.Label(
            window,
            text=(
                f"Total BNK files: {total}\n"
                f"Present: {len(found)}\n"
                f"Missing: {len(missing)}"
            ),
            font=("Arial", 11),
            bg=colors["bg"],
            fg=colors["fg"]
        )

        summary.pack(
            pady=8
        )

        missing_label = tk.Label(
            window,
            text="MISSING FILES",
            font=("Arial", 11, "bold"),
            bg=colors["bg"],
            fg=colors["error"]
        )

        missing_label.pack(
            pady=5
        )

        frame = tk.Frame(
            window,
            bg=colors["bg"]
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10
        )

        text = tk.Text(
            frame,
            wrap="none",
            font=("Consolas", 10),
            bg=colors["list_bg"],
            fg=colors["list_fg"],
            insertbackground=colors["list_fg"]
        )

        text.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar = tk.Scrollbar(
            frame,
            command=text.yview
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        text.config(
            yscrollcommand=scrollbar.set
        )

        for item in missing:

            text.insert(
                tk.END,
                item + "\n"
            )

        text.config(
            state="disabled"
        )

        button_frame = tk.Frame(
            window,
            bg=colors["bg"]
        )

        button_frame.pack(
            pady=12
        )

        retry_button = tk.Button(
            button_frame,
            text="RETRY MISSING FILES",
            width=23,
            height=2,
            bg=colors["button_bg"],
            fg=colors["button_fg"],
            activebackground=colors["select_bg"],
            activeforeground=colors["select_fg"]
        )

        retry_button.pack(
            side="left",
            padx=6
        )

        close_button = tk.Button(
            button_frame,
            text="CLOSE",
            width=15,
            height=2,
            bg=colors["button_bg"],
            fg=colors["button_fg"],
            activebackground=colors["select_bg"],
            activeforeground=colors["select_fg"],
            command=window.destroy
        )

        close_button.pack(
            side="left",
            padx=6
        )

        # ----------------------------------------------------
        # RETRY CALLBACK
        # ----------------------------------------------------

        missing_absolute = []

        bnk_root = self.config.data[
            "bnk_folder"
        ]

        for bnk_file in files:

            relative = os.path.relpath(
                bnk_file,
                bnk_root
            )

            if relative in missing:

                missing_absolute.append(
                    bnk_file
                )

        def retry_missing():

            answer = messagebox.askyesno(
                "Retry Missing Files",
                (
                    f"{len(missing_absolute)} BNK files "
                    "are missing.\n\n"
                    "Do you want to retry extraction "
                    "only for these files?\n\n"
                    "Files already verified will NOT "
                    "be processed again."
                ),
                parent=window
            )

            if not answer:
                return

            window.destroy()

            self.start_extraction(
                files=missing_absolute,
                retry_mode=True
            )

        retry_button.configure(
            command=retry_missing
        )

        self.set_status(
            f"Verification found "
            f"{len(missing)} missing BNK files."
        )


    # ========================================================
    # THEME
    # ========================================================

    def theme_changed(
        self,
        event=None
    ):

        theme = self.theme_variable.get()

        if theme not in THEMES:
            theme = "Light"

        self.config.data[
            "theme"
        ] = theme

        self.config.save()

        self.apply_theme(
            theme
        )


    def apply_theme(
        self,
        theme
    ):

        if theme not in THEMES:
            theme = "Light"

        colors = THEMES[
            theme
        ]

        self.root.configure(
            bg=colors["bg"]
        )

        labels = [
            self.title_label,
            self.output_label,
            self.structure_label,
            self.manager_info_label,
            self.speed_text_label,
            self.theme_text_label,
            self.calibration_label,
            self.bnk_title_label,
            self.count_label,
            self.status_label
        ]

        for widget in labels:

            widget.configure(
                bg=colors["bg"],
                fg=colors["fg"]
            )

        self.settings_frame.configure(
            bg=colors["bg"]
        )

        self.separator.configure(
            bg=colors["border"]
        )

        self.output_frame.configure(
            bg=colors["bg"],
            fg=colors["fg"]
        )

        self.hotkey_frame.configure(
            bg=colors["bg"],
            fg=colors["fg"]
        )

        self.hotkey_label.configure(
            bg=colors["bg"],
            fg=colors["fg"]
        )

        self.button_frame.configure(
            bg=colors["bg"]
        )

        self.bnk_list.configure(
            bg=colors["list_bg"],
            fg=colors["list_fg"],
            selectbackground=colors["select_bg"],
            selectforeground=colors["select_fg"],
            highlightbackground=colors["border"],
            highlightcolor=colors["select_bg"]
        )

        buttons = [
            self.calibration_button,
            self.test_button,
            self.start_button,
            self.stop_button,
            self.verify_button
        ]

        for button in buttons:

            button.configure(
                bg=colors["button_bg"],
                fg=colors["button_fg"],
                activebackground=colors["select_bg"],
                activeforeground=colors["select_fg"]
            )

        for widget in self.widget_registry:

            try:

                if isinstance(
                    widget,
                    tk.Frame
                ):

                    widget.configure(
                        bg=colors["bg"]
                    )

                elif isinstance(
                    widget,
                    tk.Label
                ):

                    widget.configure(
                        bg=colors["bg"],
                        fg=colors["fg"]
                    )

                elif isinstance(
                    widget,
                    tk.Entry
                ):

                    widget.configure(
                        bg=colors["entry_bg"],
                        fg=colors["entry_fg"],
                        insertbackground=colors["entry_fg"],
                        highlightbackground=colors["border"],
                        highlightcolor=colors["select_bg"]
                    )

                elif isinstance(
                    widget,
                    tk.Button
                ):

                    widget.configure(
                        bg=colors["button_bg"],
                        fg=colors["button_fg"],
                        activebackground=colors["select_bg"],
                        activeforeground=colors["select_fg"]
                    )

            except Exception:
                pass

        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )
        except Exception:
            pass

        style.configure(
            "TCombobox",
            fieldbackground=colors["entry_bg"],
            background=colors["button_bg"],
            foreground=colors["entry_fg"],
            arrowcolor=colors["fg"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"]
        )

        style.map(
            "TCombobox",
            fieldbackground=[
                (
                    "readonly",
                    colors["entry_bg"]
                )
            ],
            foreground=[
                (
                    "readonly",
                    colors["entry_fg"]
                )
            ],
            selectbackground=[
                (
                    "readonly",
                    colors["select_bg"]
                )
            ],
            selectforeground=[
                (
                    "readonly",
                    colors["select_fg"]
                )
            ]
        )


    # ========================================================
    # BUTTON STATE
    # ========================================================

    def set_buttons_running(
        self,
        running
    ):

        if running:

            self.start_button.config(
                state="disabled"
            )

            self.test_button.config(
                state="disabled"
            )

            self.verify_button.config(
                state="disabled"
            )

            self.calibration_button.config(
                state="disabled"
            )

            self.stop_button.config(
                state="normal"
            )

        else:

            self.start_button.config(
                state="normal"
            )

            self.test_button.config(
                state="normal"
            )

            self.verify_button.config(
                state="normal"
            )

            self.calibration_button.config(
                state="normal"
            )

            self.stop_button.config(
                state="disabled"
            )


    # ========================================================
    # FINISH EXTRACTION
    # ========================================================

    def finish_extraction(self):

        self.extraction_running = False

        self.root.after(
            0,
            lambda:
            self.set_buttons_running(
                False
            )
        )


    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        text
    ):

        try:

            self.root.after(
                0,
                lambda text=text:
                self.status_label.config(
                    text="Status: " + text
                )
            )

        except Exception:
            pass


    # ========================================================
    # CLOSE APPLICATION
    # ========================================================

    def on_close(self):

        if self.extraction_running:

            answer = messagebox.askyesno(
                "Exit",
                (
                    "An extraction is currently running.\n\n"
                    "Do you want to stop it and exit?"
                )
            )

            if not answer:
                return

            self.stop_requested = True

        try:

            self.hotkeys.stop()

        except Exception:
            pass

        try:

            if self.calibration_window is not None:

                self.calibration_window.close()

        except Exception:
            pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    Application(
        root
    )

    root.mainloop()


if __name__ == "__main__":

    main()
