import os
import re
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Audio Tool 3.0"


# ============================================================
# PATHS
# ============================================================

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
FFMPEG_DIR = os.path.join(BASE_DIR, "ffmpeg")

if os.name == "nt":
    FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    FFPROBE = os.path.join(FFMPEG_DIR, "ffprobe.exe")
else:
    FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg")
    FFPROBE = os.path.join(FFMPEG_DIR, "ffprobe")


# ============================================================
# CONSTANTS
# ============================================================

ADPCM_SAMPLE_RATES = [
    8000,
    11025,
    16000,
    22050,
    32000,
    44100,
    48000,
    88200,
    96000,
]

MP3_SAMPLE_RATES = [
    8000,
    11025,
    16000,
    22050,
    32000,
    44100,
    48000,
]

WAV_SAMPLE_RATES = [
    8000,
    11025,
    16000,
    22050,
    32000,
    44100,
    48000,
    88200,
    96000,
]


# ============================================================
# UTILITY
# ============================================================

def parse_duration(value):
    """
    Supported formats:

    30
    30.500
    03:45
    03:45.500
    01:03:45
    01:03:45.500
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        if re.fullmatch(r"\d+(\.\d+)?", value):
            seconds = float(value)

            if seconds >= 0:
                return seconds

            raise ValueError

        parts = value.split(":")

        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])

            if minutes < 0 or seconds < 0 or seconds >= 60:
                raise ValueError

            return minutes * 60 + seconds

        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            if (
                hours < 0
                or minutes < 0
                or seconds < 0
                or minutes >= 60
                or seconds >= 60
            ):
                raise ValueError

            return hours * 3600 + minutes * 60 + seconds

    except (ValueError, TypeError):
        pass

    raise ValueError(
        "Durata non valida.\n\n"
        "Formati supportati:\n"
        "30\n"
        "03:45\n"
        "00:03:45.500"
    )


def format_duration(seconds):
    if seconds is None:
        return "--:--:--.---"

    try:
        seconds = float(seconds)
    except (ValueError, TypeError):
        return "--:--:--.---"

    if seconds < 0:
        seconds = 0

    total_milliseconds = int(round(seconds * 1000))

    total_seconds = total_milliseconds // 1000
    milliseconds = total_milliseconds % 1000

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{milliseconds:03d}"
    )


def format_size(size):
    if size is None:
        return "N/D"

    try:
        size = float(size)
    except (ValueError, TypeError):
        return "N/D"

    units = [
        ("B", 1),
        ("KB", 1024),
        ("MB", 1024 ** 2),
        ("GB", 1024 ** 3),
    ]

    for unit, divider in reversed(units):
        if size >= divider:
            return f"{size / divider:.2f} {unit}"

    return "0 B"


def channels_to_number(value):
    return 1 if value == "Mono" else 2


def adpcm_nominal_bitrate(sample_rate, channels):
    """
    IMA ADPCM:
    4 bits per sample.
    """

    return sample_rate * 4 * channels / 1000


def closest_adpcm_sample_rate(target_kbps, channels):
    best_rate = ADPCM_SAMPLE_RATES[0]
    best_difference = float("inf")

    for rate in ADPCM_SAMPLE_RATES:
        bitrate = adpcm_nominal_bitrate(rate, channels)
        difference = abs(bitrate - target_kbps)

        if difference < best_difference:
            best_difference = difference
            best_rate = rate

    return best_rate


# ============================================================
# APPLICATION
# ============================================================

class AudioTool:

    def __init__(self, root):

        self.root = root

        self.root.title(APP_NAME)
        self.root.geometry("1050x820")
        self.root.minsize(900, 700)

        # ----------------------------------------------------
        # VARIABLES
        # ----------------------------------------------------

        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()

        self.format_var = tk.StringVar(value="MP3")

        # MP3
        self.mp3_bitrate = tk.StringVar(value="192")
        self.mp3_channels = tk.StringVar(value="Stereo")
        self.mp3_samplerate = tk.StringVar(value="44100")

        # WAV
        self.wav_type = tk.StringVar(value="PCM - Uncompressed")
        self.wav_channels = tk.StringVar(value="Stereo")
        self.wav_depth = tk.StringVar(value="16")
        self.wav_samplerate = tk.StringVar(value="44100")

        # ADPCM
        self.adpcm_target = tk.StringVar(value="177")

        # Duration
        self.duration = tk.StringVar()
        self.duration_mode = tk.StringVar(value="keep")

        # Theme
        self.theme_var = tk.StringVar(value="dark")

        # Status
        self.status = tk.StringVar(value="Ready")
        self.progress = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="0%")

        # File info
        self.source_format = tk.StringVar(value="N/D")
        self.source_duration = tk.StringVar(value="N/D")
        self.source_size = tk.StringVar(value="N/D")
        self.source_bitrate = tk.StringVar(value="N/D")
        self.source_channels = tk.StringVar(value="N/D")
        self.source_samplerate = tk.StringVar(value="N/D")

        # Export info
        self.export_format_info = tk.StringVar(value="MP3")
        self.export_codec_info = tk.StringVar(value="libmp3lame")
        self.export_channels_info = tk.StringVar(value="Stereo")
        self.export_samplerate_info = tk.StringVar(value="44100 Hz")
        self.export_bitrate_info = tk.StringVar(value="192 kbps")

        self.last_probe_info = None
        self.is_exporting = False

        # ----------------------------------------------------
        # COLORS
        # ----------------------------------------------------

        self.colors = {}

        # ----------------------------------------------------
        # STYLE
        # ----------------------------------------------------

        self.style = ttk.Style()

        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.create_interface()
        self.apply_theme("dark")

        self.update_format()
        self.update_wav_type()
        self.update_export_preview()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # ========================================================
    # THEME
    # ========================================================

    def apply_theme(self, theme):

        if theme == "dark":

            self.colors = {
                "bg": "#12161c",
                "surface": "#1b222c",
                "surface2": "#222b36",
                "border": "#303b48",
                "text": "#f1f5f9",
                "muted": "#9aa7b5",
                "accent": "#4f9cff",
                "accent_hover": "#6cabff",
                "success": "#35c759",
                "warning": "#ffb020",
                "danger": "#ff5c5c",
                "log_bg": "#0b0e12",
                "log_fg": "#c9d1d9",
                "entry": "#151b23",
            }

        else:

            self.colors = {
                "bg": "#f1f4f8",
                "surface": "#ffffff",
                "surface2": "#f7f9fc",
                "border": "#d7dee8",
                "text": "#18212b",
                "muted": "#667384",
                "accent": "#2878d8",
                "accent_hover": "#1e67bd",
                "success": "#1f9d45",
                "warning": "#c57b00",
                "danger": "#d93636",
                "log_bg": "#10151b",
                "log_fg": "#d8e0e8",
                "entry": "#ffffff",
            }

        self.root.configure(
            background=self.colors["bg"]
        )

        # ----------------------------------------------------
        # ttk general
        # ----------------------------------------------------

        self.style.configure(
            ".",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10)
        )

        self.style.configure(
            "TFrame",
            background=self.colors["bg"]
        )

        self.style.configure(
            "Surface.TFrame",
            background=self.colors["surface"]
        )

        self.style.configure(
            "TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"]
        )

        self.style.configure(
            "Surface.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"]
        )

        self.style.configure(
            "Muted.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["muted"]
        )

        self.style.configure(
            "SurfaceMuted.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["muted"]
        )

        self.style.configure(
            "Title.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Segoe UI", 24, "bold")
        )

        self.style.configure(
            "Subtitle.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["muted"],
            font=("Segoe UI", 10)
        )

        self.style.configure(
            "CardTitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 12, "bold")
        )

        self.style.configure(
            "BigStatus.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 11, "bold")
        )

        # ----------------------------------------------------
        # LabelFrame
        # ----------------------------------------------------

        self.style.configure(
            "TLabelframe",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"]
        )

        self.style.configure(
            "TLabelframe.Label",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10, "bold")
        )

        # ----------------------------------------------------
        # Entry
        # ----------------------------------------------------

        self.style.configure(
            "TEntry",
            fieldbackground=self.colors["entry"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            insertcolor=self.colors["text"]
        )

        # ----------------------------------------------------
        # Combobox
        # ----------------------------------------------------

        self.style.configure(
            "TCombobox",
            fieldbackground=self.colors["entry"],
            background=self.colors["entry"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            arrowcolor=self.colors["text"]
        )

        self.style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", self.colors["entry"])
            ],
            foreground=[
                ("readonly", self.colors["text"])
            ]
        )

        # ----------------------------------------------------
        # Button
        # ----------------------------------------------------

        self.style.configure(
            "TButton",
            background=self.colors["surface2"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            padding=(12, 7)
        )

        self.style.map(
            "TButton",
            background=[
                ("active", self.colors["accent_hover"]),
                ("pressed", self.colors["accent"]),
                ("disabled", self.colors["surface2"])
            ],
            foreground=[
                ("active", "#ffffff"),
                ("pressed", "#ffffff"),
                ("disabled", self.colors["muted"])
            ]
        )

        self.style.configure(
            "Accent.TButton",
            background=self.colors["accent"],
            foreground="#ffffff",
            padding=(20, 10),
            font=("Segoe UI", 10, "bold")
        )

        self.style.map(
            "Accent.TButton",
            background=[
                ("active", self.colors["accent_hover"]),
                ("pressed", self.colors["accent"])
            ]
        )

        self.style.configure(
            "Danger.TButton",
            background=self.colors["danger"],
            foreground="#ffffff"
        )

        # ----------------------------------------------------
        # Check / Radio
        # ----------------------------------------------------

        self.style.configure(
            "TRadiobutton",
            background=self.colors["surface"],
            foreground=self.colors["text"]
        )

        # ----------------------------------------------------
        # Progressbar
        # ----------------------------------------------------

        self.style.configure(
            "Horizontal.TProgressbar",
            background=self.colors["accent"],
            troughcolor=self.colors["surface2"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["accent"],
            darkcolor=self.colors["accent"],
            thickness=12
        )

        # ----------------------------------------------------
        # Treeview / general
        # ----------------------------------------------------

        self.style.configure(
            "Treeview",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["surface"]
        )

        # ----------------------------------------------------
        # Custom Tk widgets
        # ----------------------------------------------------

        if hasattr(self, "log_text"):
            self.log_text.configure(
                background=self.colors["log_bg"],
                foreground=self.colors["log_fg"],
                insertbackground=self.colors["log_fg"],
                selectbackground=self.colors["accent"]
            )

        if hasattr(self, "header"):
            self.header.configure(
                background=self.colors["bg"]
            )

        if hasattr(self, "main_container"):
            self.main_container.configure(
                background=self.colors["bg"]
            )

        if hasattr(self, "source_card"):
            self.source_card.configure(
                background=self.colors["surface"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["border"]
            )

        if hasattr(self, "settings_card"):
            self.settings_card.configure(
                background=self.colors["surface"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["border"]
            )

        if hasattr(self, "output_card"):
            self.output_card.configure(
                background=self.colors["surface"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["border"]
            )

        if hasattr(self, "status_card"):
            self.status_card.configure(
                background=self.colors["surface"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["border"]
            )

        if hasattr(self, "info_labels"):
            for label in self.info_labels:
                label.configure(
                    background=self.colors["surface"],
                    foreground=self.colors["text"]
                )

        if hasattr(self, "muted_labels"):
            for label in self.muted_labels:
                label.configure(
                    background=self.colors["surface"],
                    foreground=self.colors["muted"]
                )

        if hasattr(self, "theme_label"):
            self.theme_label.configure(
                background=self.colors["bg"],
                foreground=self.colors["muted"]
            )

    def toggle_theme(self, event=None):

        current = self.theme_var.get()

        if current == "dark":
            new_theme = "light"
        else:
            new_theme = "dark"

        self.theme_var.set(new_theme)
        self.apply_theme(new_theme)

    # ========================================================
    # GUI CREATION
    # ========================================================

    def create_interface(self):

        # ----------------------------------------------------
        # ROOT CONTAINER
        # ----------------------------------------------------

        self.main_container = tk.Frame(
            self.root,
            bg="#12161c"
        )

        self.main_container.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        self.header = tk.Frame(
            self.main_container,
            bg="#12161c"
        )

        self.header.pack(
            fill="x",
            padx=28,
            pady=(22, 10)
        )

        title_frame = tk.Frame(
            self.header,
            bg="#12161c"
        )

        title_frame.pack(
            side="left"
        )

        title = ttk.Label(
            title_frame,
            text="AUDIO TOOL",
            style="Title.TLabel"
        )

        title.pack(anchor="w")

        subtitle = ttk.Label(
            title_frame,
            text="Professional audio conversion utility",
            style="Subtitle.TLabel"
        )

        subtitle.pack(
            anchor="w",
            pady=(2, 0)
        )

        theme_frame = tk.Frame(
            self.header,
            bg="#12161c"
        )

        theme_frame.pack(
            side="right",
            pady=5
        )

        self.theme_label = tk.Label(
            theme_frame,
            text="THEME",
            bg="#12161c",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        )

        self.theme_label.pack(
            side="left",
            padx=(0, 8)
        )

        theme_combo = ttk.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=["dark", "light"],
            state="readonly",
            width=9
        )

        theme_combo.pack(side="left")

        theme_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.apply_theme(
                self.theme_var.get()
            )
        )

        # ----------------------------------------------------
        # SCROLLABLE AREA
        # ----------------------------------------------------

        outer = tk.Frame(
            self.main_container,
            bg="#12161c"
        )

        outer.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=(5, 20)
        )

        self.canvas = tk.Canvas(
            outer,
            bg="#12161c",
            highlightthickness=0
        )

        scrollbar = ttk.Scrollbar(
            outer,
            orient="vertical",
            command=self.canvas.yview
        )

        self.canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.content = tk.Frame(
            self.canvas,
            bg="#12161c"
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw"
        )

        self.content.bind(
            "<Configure>",
            self.update_scroll_region
        )

        self.canvas.bind(
            "<Configure>",
            self.resize_canvas_content
        )

        self.canvas.bind_all(
            "<MouseWheel>",
            self.on_mousewheel
        )

        # ----------------------------------------------------
        # SOURCE CARD
        # ----------------------------------------------------

        self.source_card = tk.Frame(
            self.content,
            bg="#1b222c",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.source_card.pack(
            fill="x",
            pady=(0, 12)
        )

        self.build_source_card()

        # ----------------------------------------------------
        # SETTINGS CARD
        # ----------------------------------------------------

        self.settings_card = tk.Frame(
            self.content,
            bg="#1b222c",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.settings_card.pack(
            fill="x",
            pady=12
        )

        self.build_settings_card()

        # ----------------------------------------------------
        # OUTPUT CARD
        # ----------------------------------------------------

        self.output_card = tk.Frame(
            self.content,
            bg="#1b222c",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.output_card.pack(
            fill="x",
            pady=12
        )

        self.build_output_card()

        # ----------------------------------------------------
        # STATUS CARD
        # ----------------------------------------------------

        self.status_card = tk.Frame(
            self.content,
            bg="#1b222c",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.status_card.pack(
            fill="x",
            pady=12
        )

        self.build_status_card()

        # ----------------------------------------------------
        # FOOTER
        # ----------------------------------------------------

        footer = ttk.Label(
            self.content,
            text="FFmpeg powered audio conversion",
            style="Muted.TLabel"
        )

        footer.pack(
            pady=(5, 15)
        )

    def update_scroll_region(self, event=None):

        self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        )

    def resize_canvas_content(self, event):

        self.canvas.itemconfigure(
            self.canvas_window,
            width=event.width
        )

    def on_mousewheel(self, event):

        try:
            self.canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units"
            )
        except Exception:
            pass

    # ========================================================
    # SOURCE CARD
    # ========================================================

    def build_source_card(self):

        inner = tk.Frame(
            self.source_card,
            bg="#1b222c"
        )

        inner.pack(
            fill="x",
            padx=18,
            pady=18
        )

        title = ttk.Label(
            inner,
            text="SOURCE FILE",
            style="CardTitle.TLabel"
        )

        title.pack(anchor="w")

        subtitle = ttk.Label(
            inner,
            text="Select the audio file you want to convert.",
            style="SurfaceMuted.TLabel"
        )

        subtitle.pack(
            anchor="w",
            pady=(2, 12)
        )

        file_frame = tk.Frame(
            inner,
            bg="#1b222c"
        )

        file_frame.pack(
            fill="x"
        )

        self.input_entry = ttk.Entry(
            file_frame,
            textvariable=self.input_file
        )

        self.input_entry.pack(
            side="left",
            fill="x",
            expand=True
        )

        ttk.Button(
            file_frame,
            text="Browse...",
            command=self.select_input
        ).pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # INFORMATION GRID
        # ----------------------------------------------------

        info_frame = tk.Frame(
            inner,
            bg="#1b222c"
        )

        info_frame.pack(
            fill="x",
            pady=(15, 0)
        )

        self.info_labels = []
        self.muted_labels = []

        self.create_info_item(
            info_frame,
            "FORMAT",
            self.source_format,
            0,
            0
        )

        self.create_info_item(
            info_frame,
            "DURATION",
            self.source_duration,
            0,
            1
        )

        self.create_info_item(
            info_frame,
            "SIZE",
            self.source_size,
            0,
            2
        )

        self.create_info_item(
            info_frame,
            "BITRATE",
            self.source_bitrate,
            1,
            0
        )

        self.create_info_item(
            info_frame,
            "CHANNELS",
            self.source_channels,
            1,
            1
        )

        self.create_info_item(
            info_frame,
            "SAMPLE RATE",
            self.source_samplerate,
            1,
            2
        )

        for col in range(3):
            info_frame.grid_columnconfigure(
                col,
                weight=1
            )

    def create_info_item(
        self,
        parent,
        caption,
        variable,
        row,
        column
    ):

        frame = tk.Frame(
            parent,
            bg="#1b222c"
        )

        frame.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=(0 if column == 0 else 10, 10),
            pady=5
        )

        label = tk.Label(
            frame,
            text=caption,
            bg="#1b222c",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        )

        label.pack(anchor="w")

        value = tk.Label(
            frame,
            textvariable=variable,
            bg="#1b222c",
            fg="#f1f5f9",
            font=("Segoe UI", 10)
        )

        value.pack(
            anchor="w",
            pady=(2, 0)
        )

        self.info_labels.append(value)
        self.muted_labels.append(label)

    # ========================================================
    # SETTINGS CARD
    # ========================================================

    def build_settings_card(self):

        inner = tk.Frame(
            self.settings_card,
            bg="#1b222c"
        )

        inner.pack(
            fill="x",
            padx=18,
            pady=18
        )

        title = ttk.Label(
            inner,
            text="EXPORT SETTINGS",
            style="CardTitle.TLabel"
        )

        title.pack(anchor="w")

        subtitle = ttk.Label(
            inner,
            text="Choose the format and conversion parameters.",
            style="SurfaceMuted.TLabel"
        )

        subtitle.pack(
            anchor="w",
            pady=(2, 14)
        )

        # ----------------------------------------------------
        # FORMAT
        # ----------------------------------------------------

        format_line = tk.Frame(
            inner,
            bg="#1b222c"
        )

        format_line.pack(
            fill="x",
            pady=(0, 10)
        )

        ttk.Label(
            format_line,
            text="Export format:"
        ).pack(side="left")

        self.format_combo = ttk.Combobox(
            format_line,
            textvariable=self.format_var,
            values=["MP3", "WAV"],
            state="readonly",
            width=18
        )

        self.format_combo.pack(
            side="left",
            padx=(12, 0)
        )

        self.format_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_format()
        )

        # ----------------------------------------------------
        # MP3 FRAME
        # ----------------------------------------------------

        self.mp3_frame = tk.Frame(
            inner,
            bg="#222b36",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.build_mp3_settings()

        # ----------------------------------------------------
        # WAV FRAME
        # ----------------------------------------------------

        self.wav_frame = tk.Frame(
            inner,
            bg="#222b36",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.build_wav_settings()

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        duration_frame = tk.Frame(
            inner,
            bg="#222b36",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        duration_frame.pack(
            fill="x",
            pady=(12, 0)
        )

        duration_inner = tk.Frame(
            duration_frame,
            bg="#222b36"
        )

        duration_inner.pack(
            fill="x",
            padx=14,
            pady=14
        )

        duration_title = tk.Label(
            duration_inner,
            text="DURATION",
            bg="#222b36",
            fg="#f1f5f9",
            font=("Segoe UI", 10, "bold")
        )

        duration_title.grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 10)
        )

        ttk.Radiobutton(
            duration_inner,
            text="Keep original",
            variable=self.duration_mode,
            value="keep",
            command=self.update_export_preview
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 18)
        )

        ttk.Radiobutton(
            duration_inner,
            text="Maximum duration",
            variable=self.duration_mode,
            value="max",
            command=self.update_export_preview
        ).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(0, 18)
        )

        ttk.Radiobutton(
            duration_inner,
            text="Exact duration",
            variable=self.duration_mode,
            value="exact",
            command=self.update_export_preview
        ).grid(
            row=1,
            column=2,
            sticky="w"
        )

        ttk.Label(
            duration_inner,
            text="Duration:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        duration_entry = ttk.Entry(
            duration_inner,
            textvariable=self.duration,
            width=18
        )

        duration_entry.grid(
            row=2,
            column=1,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Label(
            duration_inner,
            text="HH:MM:SS.mmm"
        ).grid(
            row=2,
            column=2,
            sticky="w",
            padx=10,
            pady=(10, 0)
        )

        self.duration.trace_add(
            "write",
            lambda *_: self.update_export_preview()
        )

    def build_mp3_settings(self):

        inner = tk.Frame(
            self.mp3_frame,
            bg="#222b36"
        )

        inner.pack(
            fill="x",
            padx=14,
            pady=14
        )

        tk.Label(
            inner,
            text="MP3",
            bg="#222b36",
            fg="#4f9cff",
            font=("Segoe UI", 11, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=6,
            sticky="w",
            pady=(0, 12)
        )

        ttk.Label(
            inner,
            text="Bitrate:"
        ).grid(
            row=1,
            column=0,
            sticky="w"
        )

        bitrate_entry = ttk.Entry(
            inner,
            textvariable=self.mp3_bitrate,
            width=10
        )

        bitrate_entry.grid(
            row=1,
            column=1,
            padx=(8, 4)
        )

        ttk.Label(
            inner,
            text="kbps"
        ).grid(
            row=1,
            column=2,
            sticky="w"
        )

        ttk.Label(
            inner,
            text="Channels:"
        ).grid(
            row=1,
            column=3,
            sticky="w",
            padx=(30, 6)
        )

        channels_combo = ttk.Combobox(
            inner,
            textvariable=self.mp3_channels,
            values=["Mono", "Stereo"],
            state="readonly",
            width=11
        )

        channels_combo.grid(
            row=1,
            column=4,
            sticky="w"
        )

        ttk.Label(
            inner,
            text="Sample rate:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        samplerate_combo = ttk.Combobox(
            inner,
            textvariable=self.mp3_samplerate,
            values=[str(x) for x in MP3_SAMPLE_RATES],
            state="readonly",
            width=11
        )

        samplerate_combo.grid(
            row=2,
            column=1,
            sticky="w",
            pady=(10, 0),
            padx=(8, 4)
        )

        ttk.Label(
            inner,
            text="Hz"
        ).grid(
            row=2,
            column=2,
            sticky="w",
            pady=(10, 0)
        )

        for variable in [
            self.mp3_bitrate,
            self.mp3_channels,
            self.mp3_samplerate
        ]:
            variable.trace_add(
                "write",
                lambda *_: self.update_export_preview()
            )

    def build_wav_settings(self):

        inner = tk.Frame(
            self.wav_frame,
            bg="#222b36"
        )

        inner.pack(
            fill="x",
            padx=14,
            pady=14
        )

        tk.Label(
            inner,
            text="WAV",
            bg="#222b36",
            fg="#4f9cff",
            font=("Segoe UI", 11, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(0, 12)
        )

        ttk.Label(
            inner,
            text="WAV type:"
        ).grid(
            row=1,
            column=0,
            sticky="w"
        )

        self.wav_type_combo = ttk.Combobox(
            inner,
            textvariable=self.wav_type,
            values=[
                "PCM - Uncompressed",
                "IMA ADPCM - 4 bit"
            ],
            state="readonly",
            width=26
        )

        self.wav_type_combo.grid(
            row=1,
            column=1,
            padx=10,
            sticky="w"
        )

        self.wav_type_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_wav_type()
        )

        ttk.Label(
            inner,
            text="Channels:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        wav_channels_combo = ttk.Combobox(
            inner,
            textvariable=self.wav_channels,
            values=["Mono", "Stereo"],
            state="readonly",
            width=12
        )

        wav_channels_combo.grid(
            row=2,
            column=1,
            sticky="w",
            padx=10,
            pady=(10, 0)
        )

        wav_channels_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_adpcm_info()
        )

        ttk.Label(
            inner,
            text="Bit depth:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        self.depth_combo = ttk.Combobox(
            inner,
            textvariable=self.wav_depth,
            values=["16"],
            state="readonly",
            width=12
        )

        self.depth_combo.grid(
            row=3,
            column=1,
            sticky="w",
            padx=10,
            pady=(10, 0)
        )

        ttk.Label(
            inner,
            text="bit"
        ).grid(
            row=3,
            column=2,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Label(
            inner,
            text="Sample rate:"
        ).grid(
            row=4,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        self.wav_samplerate_combo = ttk.Combobox(
            inner,
            textvariable=self.wav_samplerate,
            values=[str(x) for x in WAV_SAMPLE_RATES],
            state="readonly",
            width=12
        )

        self.wav_samplerate_combo.grid(
            row=4,
            column=1,
            sticky="w",
            padx=10,
            pady=(10, 0)
        )

        ttk.Label(
            inner,
            text="Hz"
        ).grid(
            row=4,
            column=2,
            sticky="w",
            pady=(10, 0)
        )

        # ----------------------------------------------------
        # ADPCM
        # ----------------------------------------------------

        self.adpcm_frame = tk.Frame(
            inner,
            bg="#151b23",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        self.adpcm_frame.grid(
            row=5,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(14, 0)
        )

        adpcm_inner = tk.Frame(
            self.adpcm_frame,
            bg="#151b23"
        )

        adpcm_inner.pack(
            fill="x",
            padx=12,
            pady=12
        )

        tk.Label(
            adpcm_inner,
            text="IMA ADPCM bitrate target",
            bg="#151b23",
            fg="#f1f5f9",
            font=("Segoe UI", 10, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w"
        )

        ttk.Label(
            adpcm_inner,
            text="Target bitrate:"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0)
        )

        ttk.Entry(
            adpcm_inner,
            textvariable=self.adpcm_target,
            width=10
        ).grid(
            row=1,
            column=1,
            padx=8,
            pady=(8, 0)
        )

        ttk.Label(
            adpcm_inner,
            text="kbps"
        ).grid(
            row=1,
            column=2,
            sticky="w",
            pady=(8, 0)
        )

        self.adpcm_info = tk.Label(
            adpcm_inner,
            text="",
            bg="#151b23",
            fg="#9aa7b5",
            justify="left",
            anchor="w",
            font=("Segoe UI", 9)
        )

        self.adpcm_info.grid(
            row=2,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(8, 0)
        )

        self.adpcm_target.trace_add(
            "write",
            lambda *_: self.update_adpcm_info()
        )

        self.wav_samplerate_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_export_preview()
        )

    # ========================================================
    # OUTPUT CARD
    # ========================================================

    def build_output_card(self):

        inner = tk.Frame(
            self.output_card,
            bg="#1b222c"
        )

        inner.pack(
            fill="x",
            padx=18,
            pady=18
        )

        title = ttk.Label(
            inner,
            text="OUTPUT",
            style="CardTitle.TLabel"
        )

        title.pack(anchor="w")

        subtitle = ttk.Label(
            inner,
            text="Choose where the converted audio file will be saved.",
            style="SurfaceMuted.TLabel"
        )

        subtitle.pack(
            anchor="w",
            pady=(2, 12)
        )

        output_frame = tk.Frame(
            inner,
            bg="#1b222c"
        )

        output_frame.pack(
            fill="x"
        )

        ttk.Entry(
            output_frame,
            textvariable=self.output_file
        ).pack(
            side="left",
            fill="x",
            expand=True
        )

        ttk.Button(
            output_frame,
            text="Browse...",
            command=self.select_output
        ).pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # PREVIEW
        # ----------------------------------------------------

        preview = tk.Frame(
            inner,
            bg="#222b36",
            highlightthickness=1,
            highlightbackground="#303b48"
        )

        preview.pack(
            fill="x",
            pady=(14, 0)
        )

        preview_inner = tk.Frame(
            preview,
            bg="#222b36"
        )

        preview_inner.pack(
            fill="x",
            padx=14,
            pady=12
        )

        tk.Label(
            preview_inner,
            text="EXPORT PREVIEW",
            bg="#222b36",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 8)
        )

        self.create_preview_item(
            preview_inner,
            "FORMAT",
            self.export_format_info,
            1,
            0
        )

        self.create_preview_item(
            preview_inner,
            "CODEC",
            self.export_codec_info,
            1,
            1
        )

        self.create_preview_item(
            preview_inner,
            "CHANNELS",
            self.export_channels_info,
            1,
            2
        )

        self.create_preview_item(
            preview_inner,
            "SAMPLE RATE",
            self.export_samplerate_info,
            1,
            3
        )

        self.create_preview_item(
            preview_inner,
            "BITRATE",
            self.export_bitrate_info,
            2,
            0
        )

        for col in range(4):
            preview_inner.grid_columnconfigure(
                col,
                weight=1
            )

    def create_preview_item(
        self,
        parent,
        caption,
        variable,
        row,
        column
    ):

        frame = tk.Frame(
            parent,
            bg="#222b36"
        )

        frame.grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 18),
            pady=3
        )

        tk.Label(
            frame,
            text=caption,
            bg="#222b36",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")

        tk.Label(
            frame,
            textvariable=variable,
            bg="#222b36",
            fg="#f1f5f9",
            font=("Segoe UI", 9)
        ).pack(
            anchor="w",
            pady=(2, 0)
        )

    # ========================================================
    # STATUS CARD
    # ========================================================

    def build_status_card(self):

        inner = tk.Frame(
            self.status_card,
            bg="#1b222c"
        )

        inner.pack(
            fill="x",
            padx=18,
            pady=18
        )

        top = tk.Frame(
            inner,
            bg="#1b222c"
        )

        top.pack(
            fill="x"
        )

        tk.Label(
            top,
            text="CONVERSION",
            bg="#1b222c",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        ).pack(
            side="left"
        )

        self.percent_label = tk.Label(
            top,
            textvariable=self.progress_text,
            bg="#1b222c",
            fg="#4f9cff",
            font=("Segoe UI", 10, "bold")
        )

        self.percent_label.pack(
            side="right"
        )

        self.status_label = tk.Label(
            inner,
            textvariable=self.status,
            bg="#1b222c",
            fg="#f1f5f9",
            font=("Segoe UI", 11, "bold")
        )

        self.status_label.pack(
            anchor="w",
            pady=(6, 8)
        )

        ttk.Progressbar(
            inner,
            variable=self.progress,
            maximum=100,
            mode="determinate"
        ).pack(
            fill="x"
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = tk.Frame(
            inner,
            bg="#1b222c"
        )

        buttons.pack(
            fill="x",
            pady=(15, 0)
        )

        self.export_button = ttk.Button(
            buttons,
            text="EXPORT AUDIO",
            style="Accent.TButton",
            command=self.start_export
        )

        self.export_button.pack(
            side="left"
        )

        self.open_folder_button = ttk.Button(
            buttons,
            text="Open output folder",
            command=self.open_output_folder,
            state="disabled"
        )

        self.open_folder_button.pack(
            side="left",
            padx=(10, 0)
        )

        ttk.Button(
            buttons,
            text="Clear log",
            command=self.clear_log
        ).pack(
            side="right"
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        log_title = tk.Label(
            inner,
            text="FFMPEG LOG",
            bg="#1b222c",
            fg="#9aa7b5",
            font=("Segoe UI", 8, "bold")
        )

        log_title.pack(
            anchor="w",
            pady=(18, 6)
        )

        log_frame = tk.Frame(
            inner,
            bg="#0b0e12"
        )

        log_frame.pack(
            fill="both"
        )

        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            bg="#0b0e12",
            fg="#c9d1d9",
            insertbackground="#c9d1d9",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 9)
        )

        log_scroll = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview
        )

        self.log_text.configure(
            yscrollcommand=log_scroll.set
        )

        self.log_text.pack(
            side="left",
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        log_scroll.pack(
            side="right",
            fill="y"
        )

    # ========================================================
    # FORMAT UPDATE
    # ========================================================

    def update_format(self):

        value = self.format_var.get()

        if value == "MP3":

            self.wav_frame.pack_forget()

            self.mp3_frame.pack(
                fill="x",
                pady=(4, 0)
            )

        else:

            self.mp3_frame.pack_forget()

            self.wav_frame.pack(
                fill="x",
                pady=(4, 0)
            )

            self.update_wav_type()

        self.update_default_output_if_needed()
        self.update_export_preview()

    # ========================================================
    # WAV TYPE
    # ========================================================

    def update_wav_type(self):

        value = self.wav_type.get()

        if value.startswith("PCM"):

            self.depth_combo.configure(
                values=["16"]
            )

            self.wav_depth.set("16")

            self.adpcm_frame.grid_remove()

        else:

            self.depth_combo.configure(
                values=["4"]
            )

            self.wav_depth.set("4")

            self.adpcm_frame.grid()

            self.update_adpcm_info()

        self.update_export_preview()

    # ========================================================
    # INPUT
    # ========================================================

    def select_input(self):

        filename = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[
                (
                    "Audio files",
                    "*.mp3 *.wav *.m4a *.flac *.aac *.ogg *.opus *.wma"
                ),
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("M4A", "*.m4a"),
                ("FLAC", "*.flac"),
                ("AAC", "*.aac"),
                ("OGG", "*.ogg"),
                ("OPUS", "*.opus"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        self.input_file.set(filename)

        self.load_source_info()
        self.update_default_output()

        self.status.set(
            "Source file ready."
        )

        self.progress.set(0)
        self.progress_text.set("0%")

        self.open_folder_button.configure(
            state="disabled"
        )

        self.clear_log()

        self.log(
            f"Selected source: {filename}"
        )

    def load_source_info(self):

        filename = self.input_file.get()

        if not filename or not os.path.isfile(filename):
            return

        try:

            info = self.probe_file(filename)

            self.source_format.set(
                info.get("format_name", "N/D").upper()
            )

            self.source_duration.set(
                format_duration(
                    info.get("duration")
                )
            )

            self.source_size.set(
                format_size(
                    info.get("size")
                )
            )

            bitrate = info.get("bitrate")

            if bitrate is not None:
                self.source_bitrate.set(
                    f"{bitrate:.1f} kbps"
                )
            else:
                self.source_bitrate.set("N/D")

            channels = info.get("channels")

            if channels == 1:
                self.source_channels.set("Mono")
            elif channels == 2:
                self.source_channels.set("Stereo")
            elif channels:
                self.source_channels.set(
                    f"{channels} channels"
                )
            else:
                self.source_channels.set("N/D")

            samplerate = info.get("sample_rate")

            if samplerate:
                self.source_samplerate.set(
                    f"{samplerate} Hz"
                )
            else:
                self.source_samplerate.set("N/D")

        except Exception as error:

            self.log(
                f"Unable to read source information: {error}"
            )

            self.source_format.set("N/D")
            self.source_duration.set("N/D")
            self.source_size.set("N/D")
            self.source_bitrate.set("N/D")
            self.source_channels.set("N/D")
            self.source_samplerate.set("N/D")

    # ========================================================
    # DEFAULT OUTPUT
    # ========================================================

    def update_default_output(self):

        filename = self.input_file.get()

        if not filename:
            return

        base = os.path.splitext(filename)[0]
        extension = self.format_var.get().lower()

        self.output_file.set(
            base + "_export." + extension
        )

    def update_default_output_if_needed(self):

        input_filename = self.input_file.get()
        current_output = self.output_file.get()

        if not input_filename:
            return

        default_base = os.path.splitext(input_filename)[0]

        old_extensions = [
            "_export.mp3",
            "_export.wav"
        ]

        if (
            not current_output
            or any(
                current_output == default_base + ext
                for ext in old_extensions
            )
        ):

            self.update_default_output()

    # ========================================================
    # OUTPUT
    # ========================================================

    def select_output(self):

        extension = self.format_var.get().lower()

        filename = filedialog.asksaveasfilename(
            title="Save converted audio",
            defaultextension="." + extension,
            filetypes=[
                (
                    extension.upper(),
                    "*." + extension
                ),
                (
                    "All files",
                    "*.*"
                )
            ]
        )

        if filename:
            self.output_file.set(filename)

    # ========================================================
    # ADPCM
    # ========================================================

    def update_adpcm_info(self):

        try:

            target = float(
                self.adpcm_target.get()
            )

            channels = channels_to_number(
                self.wav_channels.get()
            )

            rate = closest_adpcm_sample_rate(
                target,
                channels
            )

            bitrate = adpcm_nominal_bitrate(
                rate,
                channels
            )

            self.adpcm_info.configure(
                text=(
                    f"Recommended: {rate} Hz / "
                    f"4 bit / "
                    f"{self.wav_channels.get()}\n"
                    f"Nominal bitrate: "
                    f"{bitrate:.1f} kbps"
                )
            )

        except Exception:

            self.adpcm_info.configure(
                text="Enter a valid target bitrate."
            )

        self.update_export_preview()

    # ========================================================
    # EXPORT PREVIEW
    # ========================================================

    def update_export_preview(self):

        output_format = self.format_var.get()

        if output_format == "MP3":

            self.export_format_info.set(
                "MP3"
            )

            self.export_codec_info.set(
                "libmp3lame"
            )

            self.export_channels_info.set(
                self.mp3_channels.get()
            )

            self.export_samplerate_info.set(
                f"{self.mp3_samplerate.get()} Hz"
            )

            self.export_bitrate_info.set(
                f"{self.mp3_bitrate.get()} kbps"
            )

        else:

            self.export_format_info.set(
                "WAV"
            )

            self.export_channels_info.set(
                self.wav_channels.get()
            )

            if self.wav_type.get().startswith("PCM"):

                self.export_codec_info.set(
                    "PCM signed 16-bit"
                )

                self.export_samplerate_info.set(
                    f"{self.wav_samplerate.get()} Hz"
                )

                self.export_bitrate_info.set(
                    "Uncompressed"
                )

            else:

                channels = channels_to_number(
                    self.wav_channels.get()
                )

                try:
                    target = float(
                        self.adpcm_target.get()
                    )

                    rate = closest_adpcm_sample_rate(
                        target,
                        channels
                    )

                    bitrate = adpcm_nominal_bitrate(
                        rate,
                        channels
                    )

                    self.export_codec_info.set(
                        "IMA ADPCM 4-bit"
                    )

                    self.export_samplerate_info.set(
                        f"{rate} Hz"
                    )

                    self.export_bitrate_info.set(
                        f"{bitrate:.1f} kbps"
                    )

                except Exception:

                    self.export_codec_info.set(
                        "IMA ADPCM 4-bit"
                    )

                    self.export_samplerate_info.set(
                        "N/D"
                    )

                    self.export_bitrate_info.set(
                        "N/D"
                    )

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(self):

        if not os.path.isfile(FFMPEG):

            messagebox.showerror(
                "FFmpeg not found",
                "FFmpeg was not found.\n\n"
                "Place ffmpeg.exe in:\n\n"
                + FFMPEG_DIR
            )

            return False

        if not os.path.isfile(FFPROBE):

            messagebox.showerror(
                "FFprobe not found",
                "FFprobe was not found.\n\n"
                "Place ffprobe.exe in:\n\n"
                + FFMPEG_DIR
            )

            return False

        input_file = self.input_file.get()

        if not input_file:

            messagebox.showwarning(
                "Missing source",
                "Select an audio file."
            )

            return False

        if not os.path.isfile(input_file):

            messagebox.showerror(
                "Source error",
                "The selected file does not exist."
            )

            return False

        output_file = self.output_file.get()

        if not output_file:

            messagebox.showwarning(
                "Missing output",
                "Select the output file."
            )

            return False

        # ----------------------------------------------------
        # SAME FILE
        # ----------------------------------------------------

        try:

            if (
                os.path.abspath(input_file).lower()
                == os.path.abspath(output_file).lower()
            ):

                messagebox.showerror(
                    "Invalid output",
                    "The output file cannot be the same "
                    "as the source file."
                )

                return False

        except Exception:
            pass

        # ----------------------------------------------------
        # OUTPUT DIRECTORY
        # ----------------------------------------------------

        output_dir = os.path.dirname(
            os.path.abspath(output_file)
        )

        if not os.path.isdir(output_dir):

            try:
                os.makedirs(
                    output_dir,
                    exist_ok=True
                )

            except Exception as error:

                messagebox.showerror(
                    "Output directory error",
                    str(error)
                )

                return False

        # ----------------------------------------------------
        # MP3
        # ----------------------------------------------------

        if self.format_var.get() == "MP3":

            try:

                bitrate = int(
                    self.mp3_bitrate.get()
                )

                if bitrate <= 0:
                    raise ValueError

            except ValueError:

                messagebox.showerror(
                    "Invalid bitrate",
                    "Enter a positive MP3 bitrate."
                )

                return False

        # ----------------------------------------------------
        # ADPCM
        # ----------------------------------------------------

        if (
            self.format_var.get() == "WAV"
            and self.wav_type.get().startswith("IMA")
        ):

            try:

                target = float(
                    self.adpcm_target.get()
                )

                if target <= 0:
                    raise ValueError

            except ValueError:

                messagebox.showerror(
                    "Invalid bitrate",
                    "Enter a valid ADPCM target bitrate."
                )

                return False

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        if self.duration_mode.get() != "keep":

            try:

                duration = parse_duration(
                    self.duration.get()
                )

                if duration is None or duration <= 0:
                    raise ValueError

            except Exception as error:

                messagebox.showerror(
                    "Invalid duration",
                    str(error)
                )

                return False

        return True

    # ========================================================
    # BUILD COMMAND
    # ========================================================

    def build_command(self):

        input_file = self.input_file.get()
        output_file = self.output_file.get()

        command = [
            FFMPEG,
            "-hide_banner",
            "-y",
            "-i",
            input_file
        ]

        output_format = self.format_var.get()
        mode = self.duration_mode.get()

        # ----------------------------------------------------
        # DURATION - MAX
        # ----------------------------------------------------

        if mode == "max":

            duration = parse_duration(
                self.duration.get()
            )

            command.extend([
                "-t",
                f"{duration:.3f}"
            ])

        # ----------------------------------------------------
        # MP3
        # ----------------------------------------------------

        if output_format == "MP3":

            bitrate = int(
                self.mp3_bitrate.get()
            )

            channels = channels_to_number(
                self.mp3_channels.get()
            )

            sample_rate = int(
                self.mp3_samplerate.get()
            )

            command.extend([
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "libmp3lame",
                "-b:a",
                f"{bitrate}k"
            ])

        # ----------------------------------------------------
        # WAV
        # ----------------------------------------------------

        else:

            wav_type = self.wav_type.get()

            channels = channels_to_number(
                self.wav_channels.get()
            )

            # ------------------------------------------------
            # PCM
            # ------------------------------------------------

            if wav_type.startswith("PCM"):

                sample_rate = int(
                    self.wav_samplerate.get()
                )

                command.extend([
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    str(channels),
                    "-c:a",
                    "pcm_s16le"
                ])

            # ------------------------------------------------
            # IMA ADPCM
            # ------------------------------------------------

            else:

                target = float(
                    self.adpcm_target.get()
                )

                sample_rate = closest_adpcm_sample_rate(
                    target,
                    channels
                )

                self.wav_samplerate.set(
                    str(sample_rate)
                )

                command.extend([
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    str(channels),
                    "-c:a",
                    "adpcm_ima_wav"
                ])

        # ----------------------------------------------------
        # EXACT DURATION
        # ----------------------------------------------------

        if mode == "exact":

            duration = parse_duration(
                self.duration.get()
            )

            command.extend([
                "-af",
                f"apad=whole_dur={duration:.3f}",
                "-t",
                f"{duration:.3f}"
            ])

        command.extend([
            "-progress",
            "pipe:1",
            "-nostats",
            output_file
        ])

        return command

    # ========================================================
    # START EXPORT
    # ========================================================

    def start_export(self):

        if self.is_exporting:
            return

        if not self.validate():
            return

        # ----------------------------------------------------
        # OVERWRITE CONFIRMATION
        # ----------------------------------------------------

        output_file = self.output_file.get()

        if os.path.isfile(output_file):

            answer = messagebox.askyesno(
                "File already exists",
                "The output file already exists.\n\n"
                "Do you want to replace it?"
            )

            if not answer:
                return

        self.is_exporting = True

        self.export_button.configure(
            state="disabled"
        )

        self.open_folder_button.configure(
            state="disabled"
        )

        self.progress.set(0)
        self.progress_text.set("0%")
        self.status.set(
            "Preparing conversion..."
        )

        self.clear_log()

        self.log(
            "=========================================="
        )

        self.log(
            "AUDIO TOOL - STARTING CONVERSION"
        )

        self.log(
            "=========================================="
        )

        thread = threading.Thread(
            target=self.export_audio,
            daemon=True
        )

        thread.start()

    # ========================================================
    # EXPORT
    # ========================================================

    def export_audio(self):

        process = None

        try:

            command = self.build_command()

            self.log(
                "Command:"
            )

            self.log(
                " ".join(
                    f'"{x}"'
                    if " " in str(x)
                    else str(x)
                    for x in command
                )
            )

            self.root.after(
                0,
                self.status.set,
                "Converting..."
            )

            # ------------------------------------------------
            # DETERMINE TOTAL DURATION
            # ------------------------------------------------

            total_duration = None

            if self.duration_mode.get() != "keep":

                total_duration = parse_duration(
                    self.duration.get()
                )

            else:

                try:

                    source_info = self.probe_file(
                        self.input_file.get()
                    )

                    total_duration = source_info.get(
                        "duration"
                    )

                except Exception:
                    total_duration = None

            # ------------------------------------------------
            # START FFMPEG
            # ------------------------------------------------

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )

            # ------------------------------------------------
            # READ PROGRESS
            # ------------------------------------------------

            for line in process.stdout:

                if not line:
                    continue

                line = line.rstrip()

                if line.startswith("out_time_ms="):

                    try:

                        value = line.split(
                            "=",
                            1
                        )[1]

                        time_us = int(value)

                        current_seconds = (
                            time_us / 1_000_000
                        )

                        if total_duration:
                            percentage = (
                                current_seconds
                                / total_duration
                                * 100
                            )

                            percentage = max(
                                0,
                                min(100, percentage)
                            )

                            self.set_progress(
                                percentage
                            )

                        else:

                            # Indeterminate fallback.
                            self.root.after(
                                0,
                                self.status.set,
                                "Converting..."
                            )

                    except (ValueError, IndexError):
                        pass

                elif line.startswith("progress=end"):

                    self.set_progress(100)

                else:

                    # Keep useful FFmpeg lines in the log.
                    if line.strip():
                        self.log(line)

            return_code = process.wait()

            if return_code != 0:

                raise RuntimeError(
                    f"FFmpeg returned error code "
                    f"{return_code}."
                )

            # ------------------------------------------------
            # OUTPUT EXISTENCE
            # ------------------------------------------------

            output_file = self.output_file.get()

            if not os.path.isfile(output_file):

                raise RuntimeError(
                    "FFmpeg finished but the output file "
                    "was not created."
                )

            output_size = os.path.getsize(
                output_file
            )

            if output_size <= 0:

                raise RuntimeError(
                    "The output file is empty."
                )

            # ------------------------------------------------
            # VERIFY OUTPUT
            # ------------------------------------------------

            self.root.after(
                0,
                self.status.set,
                "Verifying output..."
            )

            info = self.probe_file(
                output_file
            )

            self.last_probe_info = info

            # ------------------------------------------------
            # FINAL
            # ------------------------------------------------

            self.set_progress(100)

            self.root.after(
                0,
                self.status.set,
                "Export completed successfully."
            )

            self.root.after(
                0,
                self.open_folder_button.configure,
                {"state": "normal"}
            )

            self.root.after(
                0,
                self.show_result,
                info
            )

        except Exception as error:

            self.log(
                f"ERROR: {error}"
            )

            self.root.after(
                0,
                self.status.set,
                "Conversion failed."
            )

            self.root.after(
                0,
                messagebox.showerror,
                "Export error",
                str(error)
            )

        finally:

            if process is not None:

                try:
                    if process.poll() is None:
                        process.kill()
                except Exception:
                    pass

            self.root.after(
                0,
                self.finish_export_state
            )

    def finish_export_state(self):

        self.is_exporting = False

        self.export_button.configure(
            state="normal"
        )

    # ========================================================
    # PROGRESS
    # ========================================================

    def set_progress(self, value):

        value = max(
            0,
            min(100, float(value))
        )

        self.root.after(
            0,
            self.progress.set,
            value
        )

        self.root.after(
            0,
            self.progress_text.set,
            f"{value:.0f}%"
        )

    # ========================================================
    # FFPROBE
    # ========================================================

    def probe_file(self, filename):

        command = [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration,size,bit_rate,format_name:"
                "stream=index,codec_name,codec_long_name,"
                "sample_rate,channels"
            ),
            "-of",
            "default=noprint_wrappers=1",
            filename
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:

            error_text = (
                result.stderr.strip()
                or "FFprobe failed."
            )

            raise RuntimeError(
                error_text
            )

        values = {}

        for line in result.stdout.splitlines():

            if "=" in line:

                key, value = line.split(
                    "=",
                    1
                )

                values[key] = value

        duration = None
        bitrate = None
        size = None
        sample_rate = None
        channels = None

        try:
            duration = float(
                values.get("duration")
            )
        except (ValueError, TypeError):
            pass

        try:
            bitrate = (
                int(values.get("bit_rate"))
                / 1000
            )
        except (ValueError, TypeError):
            pass

        try:
            size = int(
                values.get("size")
            )
        except (ValueError, TypeError):
            pass

        try:
            sample_rate = int(
                values.get("sample_rate")
            )
        except (ValueError, TypeError):
            pass

        try:
            channels = int(
                values.get("channels")
            )
        except (ValueError, TypeError):
            pass

        return {
            "duration": duration,
            "bitrate": bitrate,
            "size": size,
            "sample_rate": sample_rate,
            "channels": channels,
            "format_name": values.get(
                "format_name",
                "unknown"
            ),
            "codec_name": values.get(
                "codec_name",
                "unknown"
            ),
            "codec_long_name": values.get(
                "codec_long_name",
                "unknown"
            )
        }

    # ========================================================
    # RESULT
    # ========================================================

    def show_result(self, info):

        duration_text = format_duration(
            info.get("duration")
        )

        bitrate = info.get("bitrate")

        if bitrate is not None:
            bitrate_text = (
                f"{bitrate:.1f} kbps"
            )
        else:
            bitrate_text = "Not available"

        size_text = format_size(
            info.get("size")
        )

        format_name = info.get(
            "format_name",
            "unknown"
        ).upper()

        codec = info.get(
            "codec_name",
            "unknown"
        )

        output_file = self.output_file.get()

        message = (
            "Export completed successfully!\n\n"
            f"Format: {format_name}\n"
            f"Codec: {codec}\n"
            f"Duration: {duration_text}\n"
            f"Effective bitrate: {bitrate_text}\n"
            f"File size: {size_text}\n\n"
            f"File:\n{output_file}"
        )

        messagebox.showinfo(
            "Audio exported",
            message
        )

    # ========================================================
    # LOG
    # ========================================================

    def log(self, text):

        def write_log():

            try:

                self.log_text.insert(
                    "end",
                    str(text) + "\n"
                )

                self.log_text.see(
                    "end"
                )

            except tk.TclError:
                pass

        try:
            self.root.after(
                0,
                write_log
            )
        except Exception:
            pass

    def clear_log(self):

        try:

            self.log_text.delete(
                "1.0",
                "end"
            )

        except Exception:
            pass

    # ========================================================
    # OPEN OUTPUT FOLDER
    # ========================================================

    def open_output_folder(self):

        filename = self.output_file.get()

        if not filename:
            return

        folder = os.path.dirname(
            os.path.abspath(filename)
        )

        if not os.path.isdir(folder):
            return

        try:

            if os.name == "nt":

                os.startfile(folder)

            elif sys.platform == "darwin":

                subprocess.Popen([
                    "open",
                    folder
                ])

            else:

                subprocess.Popen([
                    "xdg-open",
                    folder
                ])

        except Exception as error:

            messagebox.showerror(
                "Unable to open folder",
                str(error)
            )

    # ========================================================
    # CLOSE
    # ========================================================

    def on_close(self):

        if self.is_exporting:

            answer = messagebox.askyesno(
                "Conversion in progress",
                "A conversion is currently running.\n\n"
                "Do you really want to close the program?"
            )

            if not answer:
                return

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    try:
        if os.name == "nt":
            root.iconname(APP_NAME)
    except Exception:
        pass

    app = AudioTool(root)

    root.mainloop()


if __name__ == "__main__":
    main()
