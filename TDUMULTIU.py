import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ctypes
import json
import os
import subprocess
import threading
import time
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(
    BASE_DIR,
    "tdu2_bnk_config.json"
)

LOG_FILE = os.path.join(
    BASE_DIR,
    "tdu2_bnk_log.txt"
)

VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F12 = 0x7B

VK_CONTROL = 0x11
VK_V = 0x56
VK_A = 0x41


DEFAULT_CONFIG = {
    "manager_exe": "",
    "bnk_folder": "",
    "output_folder": "",

    "path_field": None,
    "load": None,
    "unpack_all": None,
    "ok": None
}


# ============================================================
# SPEED SETTINGS
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
# WINDOWS API
# ============================================================

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

    return point.x, point.y


def move_mouse(x, y):

    user32.SetCursorPos(
        int(x),
        int(y)
    )


def mouse_click(x, y, speed):

    move_mouse(x, y)

    time.sleep(
        speed["mouse"]
    )

    user32.mouse_event(
        0x0002,
        0,
        0,
        0,
        0
    )

    time.sleep(
        speed["click"]
    )

    user32.mouse_event(
        0x0004,
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

    time.sleep(0.03)

    key_up(key)


def hotkey(key1, key2):

    key_down(key1)

    time.sleep(0.03)

    key_down(key2)

    time.sleep(0.03)

    key_up(key2)

    time.sleep(0.03)

    key_up(key1)


def key_pressed(vk_code):

    return bool(
        user32.GetAsyncKeyState(vk_code) & 0x8000
    )


def f12_pressed():

    return key_pressed(VK_F12)


# ============================================================
# CONFIGURATION MANAGER
# ============================================================

class ConfigManager:

    def __init__(self):

        self.data = dict(
            DEFAULT_CONFIG
        )

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

                saved = json.load(file)

            if isinstance(
                saved,
                dict
            ):

                for key in DEFAULT_CONFIG:

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

            messagebox.showerror(
                "Error",
                str(error)
            )

            return False


    def calibrated(self):

        return (
            self.data["path_field"] is not None
            and
            self.data["load"] is not None
            and
            self.data["unpack_all"] is not None
            and
            self.data["ok"] is not None
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

                    file.write(line)

        except Exception as error:

            print(
                "Log writing error:",
                error
            )


    def start_session(self, total):

        separator = (
            "\n"
            + "=" * 70
            + "\n"
        )

        try:

            with self.lock:

                with open(
                    LOG_FILE,
                    "a",
                    encoding="utf-8"
                ) as file:

                    file.write(separator)

                    file.write(
                        "TDU2 BNK AUTO UNPACKER\n"
                    )

                    file.write(
                        "New session\n"
                    )

                    file.write(
                        f"BNK files found: {total}\n"
                    )

                    file.write(
                        f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                    )

                    file.write(
                        "=" * 70
                        + "\n"
                    )

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

        self.write("")

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
            f"Interrupted: {'YES' if interrupted else 'NO'}"
        )

        self.write(
            "=" * 70
        )


# ============================================================
# GLOBAL HOTKEY MANAGER
# ============================================================

class GlobalHotkeyManager:

    def __init__(self, application):

        self.application = application

        self.running = True

        self.thread = threading.Thread(
            target=self.worker,
            daemon=True
        )

        self.last_state = {
            VK_F5: False,
            VK_F6: False,
            VK_F7: False,
            VK_F8: False,
            VK_F9: False
        }

        self.thread.start()


    def is_down(self, vk_code):

        return bool(
            user32.GetAsyncKeyState(vk_code) & 0x8000
        )


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

                time.sleep(0.05)

            except Exception as error:

                print(
                    "Hotkey manager error:",
                    error
                )


    def check_key(
        self,
        vk_code,
        callback
    ):

        current = self.is_down(
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
        callback
    ):

        self.parent = parent
        self.config = config
        self.callback = callback

        self.running = True
        self.step = 0

        self.steps = [

            (
                "PATH FIELD",
                "the field where the BNK path must be entered"
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
            "620x460"
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

        self.update_instruction()
        self.update_mouse()
        self.check_f12()


    def create_interface(self):

        tk.Label(
            self.window,
            text="POSITION CONFIGURATION",
            font=("Arial", 18, "bold")
        ).pack(
            pady=15
        )

        self.step_label = tk.Label(
            self.window,
            text=""
        )

        self.step_label.pack()

        self.instruction = tk.Label(
            self.window,
            text="",
            font=("Arial", 11),
            justify="center"
        )

        self.instruction.pack(
            pady=20
        )

        frame = tk.Frame(
            self.window,
            bd=2,
            relief="groove"
        )

        frame.pack(
            padx=40,
            fill="x"
        )

        tk.Label(
            frame,
            text="MOUSE POSITION",
            font=("Arial", 10, "bold")
        ).pack(
            pady=8
        )

        self.position_label = tk.Label(
            frame,
            text="X: 0    Y: 0",
            font=("Courier New", 20, "bold"),
            fg="blue"
        )

        self.position_label.pack(
            pady=12
        )

        self.status_label = tk.Label(
            self.window,
            text=""
        )

        self.status_label.pack(
            pady=10
        )

        tk.Label(
            self.window,
            text="Move the cursor and press F12",
            font=("Arial", 11, "bold"),
            fg="green"
        ).pack(
            pady=5
        )

        tk.Button(
            self.window,
            text="CANCEL",
            width=15,
            command=self.close
        ).pack(
            pady=15
        )


    def update_instruction(self):

        name, description = self.steps[
            self.step
        ]

        self.step_label.config(
            text=f"{self.step + 1} / 4    {name}"
        )

        self.instruction.config(
            text=(
                f"Move the cursor over {description}.\n\n"
                "Do not click.\n"
                "Press F12 to save the position."
            )
        )


    def update_mouse(self):

        if not self.running:
            return

        x, y = get_mouse_position()

        self.position_label.config(
            text=f"X: {x}    Y: {y}"
        )

        self.window.after(
            50,
            self.update_mouse
        )


    def check_f12(self):

        if not self.running:
            return

        if f12_pressed():

            x, y = get_mouse_position()

            self.save_position(
                x,
                y
            )

            self.wait_release()

        else:

            self.window.after(
                80,
                self.check_f12
            )


    def wait_release(self):

        if not self.running:
            return

        if f12_pressed():

            self.window.after(
                50,
                self.wait_release
            )

        else:

            self.window.after(
                80,
                self.check_f12
            )


    def save_position(
        self,
        x,
        y
    ):

        name = self.steps[
            self.step
        ][0]

        position = [
            x,
            y
        ]

        if name == "PATH FIELD":

            self.config.data[
                "path_field"
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

        self.status_label.config(
            text=(
                f"{name} saved: "
                f"X={x} Y={y}"
            ),
            fg="green"
        )

        self.step += 1

        if self.step >= 4:

            messagebox.showinfo(
                "Configuration Complete",
                "Positions saved:\n\n"
                "PATH FIELD ✓\n"
                "LOAD ✓\n"
                "UNPACK ALL ✓\n"
                "OK ✓"
            )

            self.close()

        else:

            self.update_instruction()


    def close(self):

        self.running = False

        try:

            self.window.destroy()

        except Exception:
            pass

        if self.callback:

            self.callback()


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
            "850x850"
        )

        self.root.resizable(
            False,
            False
        )

        self.config = ConfigManager()

        self.log = LogManager()

        self.stop_requested = False

        self.current_files = []

        self.completed_files = set()

        self.error_files = set()

        self.extraction_running = False

        self.calibration_window = None

        self.create_interface()

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

        tk.Label(
            self.root,
            text="TDU2 BNK AUTO UNPACKER",
            font=("Arial", 20, "bold")
        ).pack(
            pady=15
        )

        self.create_path_row(
            "Mini BNK Manager:",
            "manager_exe",
            self.select_exe
        )

        self.create_path_row(
            "BNK Folder:",
            "bnk_folder",
            self.select_bnk_folder
        )

        self.create_path_row(
            "Extraction Folder:",
            "output_folder",
            self.select_output_folder
        )

        # ----------------------------------------------------
        # SPEED
        # ----------------------------------------------------

        speed_frame = tk.Frame(
            self.root
        )

        speed_frame.pack(
            pady=8
        )

        tk.Label(
            speed_frame,
            text="Speed:"
        ).pack(
            side="left",
            padx=5
        )

        self.speed_variable = tk.StringVar(
            value="Fast"
        )

        self.speed_combo = ttk.Combobox(
            speed_frame,
            textvariable=self.speed_variable,
            values=[
                "Safe",
                "Fast",
                "Turbo"
            ],
            state="readonly",
            width=15
        )

        self.speed_combo.pack(
            side="left"
        )

        tk.Label(
            speed_frame,
            text="  Turbo = faster, but less tolerant of delays",
            fg="gray"
        ).pack(
            side="left"
        )

        # ----------------------------------------------------
        # SEPARATOR
        # ----------------------------------------------------

        tk.Frame(
            self.root,
            height=2,
            bg="gray"
        ).pack(
            fill="x",
            padx=30,
            pady=12
        )

        # ----------------------------------------------------
        # CALIBRATION BUTTON
        # ----------------------------------------------------

        tk.Button(
            self.root,
            text="CONFIGURE POSITIONS",
            width=30,
            height=2,
            font=("Arial", 10, "bold"),
            command=self.open_calibration
        ).pack(
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

        hotkey_frame = tk.LabelFrame(
            self.root,
            text="Keyboard Shortcuts",
            padx=10,
            pady=8
        )

        hotkey_frame.pack(
            padx=40,
            pady=8,
            fill="x"
        )

        hotkeys_text = (
            "F5  = Start Extraction     "
            "F6  = Stop\n"
            "F7  = Test Positions       "
            "F8  = Verify Extraction\n"
            "F9  = Configure Positions  "
            "F12 = Calibration"
        )

        tk.Label(
            hotkey_frame,
            text=hotkeys_text,
            font=("Consolas", 10),
            justify="center"
        ).pack()

        # ----------------------------------------------------
        # BNK LIST
        # ----------------------------------------------------

        tk.Label(
            self.root,
            text="BNK FILES FOUND",
            font=("Arial", 11, "bold")
        ).pack(
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
            width=92,
            height=10
        )

        self.bnk_list.pack(
            side="left"
        )

        scrollbar = tk.Scrollbar(
            list_frame,
            command=self.bnk_list.yview
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.bnk_list.config(
            yscrollcommand=scrollbar.set
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

        button_frame = tk.Frame(
            self.root
        )

        button_frame.pack(
            pady=12
        )

        self.test_button = tk.Button(
            button_frame,
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
            button_frame,
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
            button_frame,
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
            button_frame,
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

        tk.Label(
            frame,
            text=label,
            width=23,
            anchor="w"
        ).pack(
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

        tk.Entry(
            frame,
            textvariable=variable
        ).pack(
            side="left",
            fill="x",
            expand=True
        )

        tk.Button(
            frame,
            text="BROWSE",
            command=command
        ).pack(
            side="left",
            padx=5
        )


    # ========================================================
    # SELECT EXE
    # ========================================================

    def select_exe(self):

        path = filedialog.askopenfilename(
            title="Select Mini BNK Manager",
            filetypes=[
                ("Windows Programs", "*.exe"),
                ("All Files", "*.*")
            ]
        )

        if path:

            self.config.data[
                "manager_exe"
            ] = path

            self.manager_exe_variable.set(
                path
            )

            self.config.save()


    # ========================================================
    # SELECT BNK FOLDER
    # ========================================================

    def select_bnk_folder(self):

        path = filedialog.askdirectory(
            title="Select BNK Folder"
        )

        if path:

            self.config.data[
                "bnk_folder"
            ] = path

            self.bnk_folder_variable.set(
                path
            )

            self.config.save()

            self.refresh_bnk_list()


    # ========================================================
    # SELECT OUTPUT FOLDER
    # ========================================================

    def select_output_folder(self):

        path = filedialog.askdirectory(
            title="Select Extraction Folder"
        )

        if path:

            self.config.data[
                "output_folder"
            ] = path

            self.output_folder_variable.set(
                path
            )

            self.config.save()


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

        if not os.path.isdir(folder):
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
            text=f"BNK files found: {len(files)}"
        )


    # ========================================================
    # CALIBRATION STATUS
    # ========================================================

    def update_calibration_status(self):

        if self.config.calibrated():

            self.calibration_label.config(
                text="✓ Calibration complete",
                fg="green"
            )

        else:

            self.calibration_label.config(
                text="⚠ Calibration required",
                fg="darkorange"
            )


    # ========================================================
    # OPEN CALIBRATION
    # ========================================================

    def open_calibration(self):

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
            self.update_calibration_status
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
                "Complete the calibration first."
            )

            return

        answer = messagebox.askyesno(
            "Test Positions",
            "The test will move the mouse to these four positions:\n\n"
            "PATH FIELD\n"
            "LOAD\n"
            "UNPACK ALL\n"
            "OK\n\n"
            "Continue?"
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

            self.set_status(
                f"Testing {name}..."
            )

            move_mouse(
                position[0],
                position[1]
            )

            time.sleep(1)

        self.set_status(
            "Position test completed."
        )


    # ========================================================
    # START EXTRACTION
    # ========================================================

    def start_extraction(self):

        if self.extraction_running:

            return

        files = self.find_bnk_files()

        if not files:

            messagebox.showwarning(
                "BNK Files",
                "No .bnk files were found."
            )

            return

        if not self.config.calibrated():

            messagebox.showwarning(
                "Calibration",
                "Complete the calibration first."
            )

            return

        manager = self.config.data[
            "manager_exe"
        ]

        if not manager:

            messagebox.showwarning(
                "Mini BNK Manager",
                "Select Mini BNK Manager.exe."
            )

            return

        if not os.path.isfile(
            manager
        ):

            messagebox.showerror(
                "Error",
                "Mini BNK Manager.exe does not exist."
            )

            return

        output_folder = self.config.data[
            "output_folder"
        ]

        if not output_folder:

            messagebox.showwarning(
                "Output",
                "Select the extraction folder."
            )

            return

        try:

            os.makedirs(
                output_folder,
                exist_ok=True
            )

        except Exception as error:

            messagebox.showerror(
                "Output Error",
                str(error)
            )

            return

        speed_name = self.speed_variable.get()

        answer = messagebox.askyesno(
            "Start Extraction",
            f"BNK files found: {len(files)}\n"
            f"Speed: {speed_name}\n\n"
            "The original folder structure will be "
            "preserved inside the output folder.\n\n"
            "Continue?"
        )

        if not answer:
            return

        self.stop_requested = False

        self.completed_files = set()

        self.error_files = set()

        self.extraction_running = True

        self.start_button.config(
            state="disabled"
        )

        self.test_button.config(
            state="disabled"
        )

        self.verify_button.config(
            state="disabled"
        )

        self.stop_button.config(
            state="normal"
        )

        threading.Thread(
            target=self.extraction_worker,
            args=(files, speed_name),
            daemon=True
        ).start()


    # ========================================================
    # CREATE OUTPUT FOLDER
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

        output_root = os.path.abspath(
            self.config.data[
                "output_folder"
            ]
        )

        relative_dir = os.path.relpath(
            os.path.dirname(
                bnk_file
            ),
            bnk_root
        )

        if relative_dir == ".":
            relative_dir = ""

        destination = os.path.join(
            output_root,
            relative_dir
        )

        os.makedirs(
            destination,
            exist_ok=True
        )

        return destination


    # ========================================================
    # EXTRACTION WORKER
    # ========================================================

    def extraction_worker(
        self,
        files,
        speed_name
    ):

        speed = SPEEDS[
            speed_name
        ]

        total = len(files)

        completed = 0

        errors = 0

        self.log.start_session(
            total
        )

        try:

            self.set_status(
                "Starting Mini BNK Manager..."
            )

            subprocess.Popen(
                [
                    self.config.data[
                        "manager_exe"
                    ]
                ]
            )

        except Exception as error:

            self.log.write(
                f"ERROR starting Mini BNK Manager: {error}"
            )

            self.root.after(
                0,
                lambda:
                messagebox.showerror(
                    "Error",
                    "Unable to start Mini BNK Manager:\n\n"
                    + str(error)
                )
            )

            self.finish_extraction()

            return

        time.sleep(2)

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

                self.set_status(
                    f"{index}/{total} - {relative}"
                )

                self.log.write(
                    f"START: {relative}"
                )

                self.log.write(
                    f"Expected output: {output_for_bnk}"
                )

                # ------------------------------------------------
                # CLIPBOARD
                # ------------------------------------------------

                self.root.clipboard_clear()

                self.root.clipboard_append(
                    os.path.normpath(
                        bnk_file
                    )
                )

                self.root.update()

                time.sleep(
                    speed["paste"]
                )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # PATH FIELD
                # ------------------------------------------------

                path_field = self.config.data[
                    "path_field"
                ]

                mouse_click(
                    path_field[0],
                    path_field[1],
                    speed
                )

                # ------------------------------------------------
                # CTRL + A
                # ------------------------------------------------

                hotkey(
                    VK_CONTROL,
                    VK_A
                )

                time.sleep(
                    0.03
                )

                # ------------------------------------------------
                # CTRL + V
                # ------------------------------------------------

                hotkey(
                    VK_CONTROL,
                    VK_V
                )

                time.sleep(
                    speed["paste"]
                )

                if self.stop_requested:
                    break

                # ------------------------------------------------
                # LOAD
                # ------------------------------------------------

                load = self.config.data[
                    "load"
                ]

                self.set_status(
                    f"{index}/{total} - LOAD - {relative}"
                )

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

                unpack = self.config.data[
                    "unpack_all"
                ]

                self.set_status(
                    f"{index}/{total} - UNPACK ALL - {relative}"
                )

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

                ok = self.config.data[
                    "ok"
                ]

                self.set_status(
                    f"{index}/{total} - OK - {relative}"
                )

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
                # COMPLETED
                # ------------------------------------------------

                completed += 1

                self.completed_files.add(
                    os.path.normcase(
                        os.path.abspath(
                            bnk_file
                        )
                    )
                )

                self.log.write(
                    f"OK: {relative}"
                )

            except Exception as error:

                errors += 1

                self.error_files.add(
                    os.path.normcase(
                        os.path.abspath(
                            bnk_file
                        )
                    )
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
                f"Extraction completed - "
                f"{completed}/{total} OK, "
                f"{errors} errors."
            )

        self.finish_extraction()


    # ========================================================
    # STOP
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

    def verify_extraction(self):

        if self.extraction_running:

            return

        files = self.find_bnk_files()

        if not files:

            messagebox.showwarning(
                "Verification",
                "No BNK files were found."
            )

            return

        output_folder = self.config.data.get(
            "output_folder",
            ""
        )

        if not output_folder:

            messagebox.showwarning(
                "Verification",
                "Select the extraction folder first."
            )

            return

        self.set_status(
            "Verifying extraction..."
        )

        threading.Thread(
            target=self.verify_worker,
            args=(files,),
            daemon=True
        ).start()


    def verify_worker(
        self,
        files
    ):

        total = len(files)

        found = []

        missing = []

        base = os.path.abspath(
            self.config.data[
                "bnk_folder"
            ]
        )

        output_root = os.path.abspath(
            self.config.data[
                "output_folder"
            ]
        )

        for bnk_file in files:

            relative = os.path.relpath(
                bnk_file,
                base
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

            expected_folder = os.path.join(
                output_root,
                relative_dir,
                name_without_ext
            )

            # ------------------------------------------------
            # MAIN CHECK
            # ------------------------------------------------

            if os.path.isdir(
                expected_folder
            ):

                found.append(
                    relative
                )

            else:

                # ------------------------------------------------
                # ALTERNATIVE CHECK
                # ------------------------------------------------

                expected_parent = os.path.join(
                    output_root,
                    relative_dir
                )

                if os.path.isdir(
                    expected_parent
                ):

                    try:

                        contents = os.listdir(
                            expected_parent
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
                total,
                found,
                missing
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

        report_file = os.path.join(
            BASE_DIR,
            "tdu2_bnk_verification.txt"
        )

        try:

            with open(
                report_file,
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
                    f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                )

                file.write(
                    f"Total BNK files: {total}\n"
                )

                file.write(
                    f"BNK files found in output: {len(found)}\n"
                )

                file.write(
                    f"Missing BNK files: {len(missing)}\n\n"
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
                f"Error creating verification report: {error}"
            )


    # ========================================================
    # VERIFICATION RESULT
    # ========================================================

    def show_verification_result(
        self,
        total,
        found,
        missing
    ):

        if not missing:

            messagebox.showinfo(
                "Verification Complete",
                "✓ EXTRACTION COMPLETE\n\n"
                f"Total BNK files: {total}\n"
                f"BNK files in output: {len(found)}\n"
                "Missing BNK files: 0\n\n"
                "No missing BNK files were detected."
            )

            self.set_status(
                f"Verification OK - {total}/{total} BNK files present."
            )

            return

        # ----------------------------------------------------
        # MISSING FILES WINDOW
        # ----------------------------------------------------

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "Missing BNK Files"
        )

        window.geometry(
            "700x500"
        )

        window.resizable(
            True,
            True
        )

        tk.Label(
            window,
            text="EXTRACTION VERIFICATION",
            font=("Arial", 16, "bold")
        ).pack(
            pady=12
        )

        tk.Label(
            window,
            text=(
                f"Total BNK files: {total}\n"
                f"Present: {len(found)}\n"
                f"Missing: {len(missing)}"
            ),
            font=("Arial", 11)
        ).pack(
            pady=8
        )

        tk.Label(
            window,
            text="MISSING FILES:",
            font=("Arial", 11, "bold"),
            fg="red"
        ).pack(
            pady=5
        )

        frame = tk.Frame(
            window
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
            font=("Consolas", 10)
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

        tk.Button(
            window,
            text="CLOSE",
            width=15,
            command=window.destroy
        ).pack(
            pady=12
        )

        self.set_status(
            f"Verification: {len(missing)} BNK files missing."
        )


    # ========================================================
    # FINISH EXTRACTION
    # ========================================================

    def finish_extraction(self):

        self.extraction_running = False

        self.root.after(
            0,
            lambda:
            self.start_button.config(
                state="normal"
            )
        )

        self.root.after(
            0,
            lambda:
            self.test_button.config(
                state="normal"
            )
        )

        self.root.after(
            0,
            lambda:
            self.verify_button.config(
                state="normal"
            )
        )

        self.root.after(
            0,
            lambda:
            self.stop_button.config(
                state="disabled"
            )
        )


    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        text
    ):

        self.root.after(
            0,
            lambda:
            self.status_label.config(
                text="Status: " + text
            )
        )


    # ========================================================
    # APPLICATION CLOSE
    # ========================================================

    def on_close(self):

        if self.extraction_running:

            answer = messagebox.askyesno(
                "Exit",
                "An extraction is currently running.\n\n"
                "Do you want to stop it and exit?"
            )

            if not answer:

                return

            self.stop_requested = True

        try:

            self.hotkeys.stop()

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
