import os
import re
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Audio Tool 2.0"


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
# UTILITY
# ============================================================

def parse_duration(value):
    """
    Accepted formats:

    30
    30.500
    03:45
    03:45.500
    01:03:45
    01:03:45.500
    """

    value = value.strip()

    if not value:
        return None

    try:
        if re.fullmatch(r"\d+(\.\d+)?", value):
            seconds = float(value)
            return seconds if seconds >= 0 else None

        parts = value.split(":")

        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])

            if seconds >= 60:
                raise ValueError

            return minutes * 60 + seconds

        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            if minutes >= 60 or seconds >= 60:
                raise ValueError

            return hours * 3600 + minutes * 60 + seconds

    except ValueError:
        pass

    raise ValueError(
        "Invalid duration.\n\n"
        "Use one of the following formats:\n"
        "30\n"
        "03:45\n"
        "00:03:45.500"
    )


def format_duration(seconds):
    if seconds is None:
        return "--:--:--.---"

    milliseconds = int(round((seconds % 1) * 1000))

    if milliseconds >= 1000:
        seconds = int(seconds) + 1
        milliseconds = 0

    total_seconds = int(seconds)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


# ============================================================
# ADPCM
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
    96000
]


def adpcm_nominal_bitrate(sample_rate, channels):
    """
    IMA ADPCM WAV:
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
# PROGRAM
# ============================================================

class AudioTool:

    def __init__(self, root):

        self.root = root

        self.root.title(APP_NAME)
        self.root.geometry("720x720")
        self.root.minsize(680, 650)

        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()

        self.format_var = tk.StringVar(value="MP3")

        # MP3
        self.mp3_bitrate = tk.StringVar(value="192")
        self.mp3_channels = tk.StringVar(value="Stereo")
        self.mp3_samplerate = tk.StringVar(value="44100")

        # WAV
        self.wav_type = tk.StringVar(value="PCM")
        self.wav_channels = tk.StringVar(value="Stereo")
        self.wav_depth = tk.StringVar(value="16")
        self.wav_samplerate = tk.StringVar(value="44100")

        # ADPCM target
        self.adpcm_target = tk.StringVar(value="177")

        # Duration
        self.duration = tk.StringVar()
        self.duration_mode = tk.StringVar(value="keep")

        # Status
        self.status = tk.StringVar(value="Ready")
        self.progress = tk.DoubleVar(value=0)

        self.create_interface()

        self.update_format()
        self.update_wav_type()

    # ========================================================
    # GUI
    # ========================================================

    def create_interface(self):

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        title = ttk.Label(
            main,
            text="AUDIO TOOL",
            font=("Segoe UI", 22, "bold")
        )
        title.pack(pady=(0, 4))

        subtitle = ttk.Label(
            main,
            text="MP3 / WAV PCM / WAV IMA ADPCM",
            font=("Segoe UI", 10)
        )
        subtitle.pack(pady=(0, 20))

        # ----------------------------------------------------
        # INPUT
        # ----------------------------------------------------

        ttk.Label(
            main,
            text="Audio file:"
        ).pack(anchor="w")

        frame = ttk.Frame(main)
        frame.pack(fill="x", pady=(5, 15))

        ttk.Entry(
            frame,
            textvariable=self.input_file
        ).pack(side="left", fill="x", expand=True)

        ttk.Button(
            frame,
            text="Browse...",
            command=self.select_input
        ).pack(side="left", padx=(8, 0))

        # ----------------------------------------------------
        # FORMAT
        # ----------------------------------------------------

        format_frame = ttk.LabelFrame(
            main,
            text="Export format",
            padding=12
        )
        format_frame.pack(fill="x", pady=5)

        ttk.Label(
            format_frame,
            text="Format:"
        ).grid(row=0, column=0, sticky="w")

        self.format_combo = ttk.Combobox(
            format_frame,
            textvariable=self.format_var,
            values=["MP3", "WAV"],
            state="readonly",
            width=15
        )

        self.format_combo.grid(
            row=0,
            column=1,
            sticky="w",
            padx=10
        )

        self.format_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_format()
        )

        # ----------------------------------------------------
        # MP3 FRAME
        # ----------------------------------------------------

        self.mp3_frame = ttk.Frame(
            format_frame
        )

        self.mp3_frame.grid(
            row=1,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(15, 0)
        )

        ttk.Label(
            self.mp3_frame,
            text="Bitrate:"
        ).grid(row=0, column=0, sticky="w")

        ttk.Entry(
            self.mp3_frame,
            textvariable=self.mp3_bitrate,
            width=10
        ).grid(row=0, column=1, padx=8)

        ttk.Label(
            self.mp3_frame,
            text="kbps"
        ).grid(row=0, column=2, sticky="w")

        ttk.Label(
            self.mp3_frame,
            text="Channels:"
        ).grid(row=0, column=3, padx=(25, 5))

        ttk.Combobox(
            self.mp3_frame,
            textvariable=self.mp3_channels,
            values=["Mono", "Stereo"],
            state="readonly",
            width=10
        ).grid(row=0, column=4)

        ttk.Label(
            self.mp3_frame,
            text="Sample rate:"
        ).grid(row=1, column=0, pady=(10, 0))

        ttk.Combobox(
            self.mp3_frame,
            textvariable=self.mp3_samplerate,
            values=[
                "8000",
                "11025",
                "16000",
                "22050",
                "32000",
                "44100",
                "48000"
            ],
            state="readonly",
            width=10
        ).grid(row=1, column=1, pady=(10, 0))

        ttk.Label(
            self.mp3_frame,
            text="Hz"
        ).grid(row=1, column=2, sticky="w", pady=(10, 0))

        # ----------------------------------------------------
        # WAV FRAME
        # ----------------------------------------------------

        self.wav_frame = ttk.Frame(
            format_frame
        )

        self.wav_frame.grid(
            row=1,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(15, 0)
        )

        ttk.Label(
            self.wav_frame,
            text="WAV type:"
        ).grid(row=0, column=0, sticky="w")

        self.wav_type_combo = ttk.Combobox(
            self.wav_frame,
            textvariable=self.wav_type,
            values=[
                "PCM - Uncompressed",
                "IMA ADPCM - 4 bit"
            ],
            state="readonly",
            width=25
        )

        self.wav_type_combo.grid(
            row=0,
            column=1,
            padx=10
        )

        self.wav_type_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_wav_type()
        )

        ttk.Label(
            self.wav_frame,
            text="Channels:"
        ).grid(row=1, column=0, pady=(12, 0))

        ttk.Combobox(
            self.wav_frame,
            textvariable=self.wav_channels,
            values=["Mono", "Stereo"],
            state="readonly",
            width=12
        ).grid(
            row=1,
            column=1,
            sticky="w",
            padx=10,
            pady=(12, 0)
        )

        ttk.Label(
            self.wav_frame,
            text="Bit depth:"
        ).grid(row=2, column=0, pady=(12, 0))

        self.depth_combo = ttk.Combobox(
            self.wav_frame,
            textvariable=self.wav_depth,
            values=["16"],
            state="readonly",
            width=12
        )

        self.depth_combo.grid(
            row=2,
            column=1,
            sticky="w",
            padx=10,
            pady=(12, 0)
        )

        ttk.Label(
            self.wav_frame,
            text="bit"
        ).grid(row=2, column=2, sticky="w")

        ttk.Label(
            self.wav_frame,
            text="Sample rate:"
        ).grid(row=3, column=0, pady=(12, 0))

        self.wav_samplerate_combo = ttk.Combobox(
            self.wav_frame,
            textvariable=self.wav_samplerate,
            values=[
                "8000",
                "11025",
                "16000",
                "22050",
                "32000",
                "44100",
                "48000",
                "88200",
                "96000"
            ],
            state="readonly",
            width=12
        )

        self.wav_samplerate_combo.grid(
            row=3,
            column=1,
            sticky="w",
            padx=10,
            pady=(12, 0)
        )

        ttk.Label(
            self.wav_frame,
            text="Hz"
        ).grid(row=3, column=2, sticky="w")

        # ----------------------------------------------------
        # ADPCM TARGET
        # ----------------------------------------------------

        self.adpcm_frame = ttk.Frame(
            self.wav_frame
        )

        self.adpcm_frame.grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(15, 0)
        )

        ttk.Label(
            self.adpcm_frame,
            text="Target bitrate:"
        ).grid(row=0, column=0)

        ttk.Entry(
            self.adpcm_frame,
            textvariable=self.adpcm_target,
            width=10
        ).grid(row=0, column=1, padx=8)

        ttk.Label(
            self.adpcm_frame,
            text="kbps"
        ).grid(row=0, column=2)

        self.adpcm_info = ttk.Label(
            self.adpcm_frame,
            text=""
        )

        self.adpcm_info.grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(8, 0)
        )

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        duration_frame = ttk.LabelFrame(
            main,
            text="Duration",
            padding=12
        )

        duration_frame.pack(
            fill="x",
            pady=15
        )

        ttk.Label(
            duration_frame,
            text="Duration:"
        ).grid(row=0, column=0, sticky="w")

        ttk.Entry(
            duration_frame,
            textvariable=self.duration,
            width=20
        ).grid(
            row=0,
            column=1,
            padx=10
        )

        ttk.Label(
            duration_frame,
            text="HH:MM:SS.mmm"
        ).grid(row=0, column=2, sticky="w")

        ttk.Radiobutton(
            duration_frame,
            text="Keep original",
            variable=self.duration_mode,
            value="keep"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Radiobutton(
            duration_frame,
            text="Maximum duration",
            variable=self.duration_mode,
            value="max"
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Radiobutton(
            duration_frame,
            text="Exact duration",
            variable=self.duration_mode,
            value="exact"
        ).grid(row=3, column=0, columnspan=3, sticky="w")

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        ttk.Label(
            main,
            text="Output file:"
        ).pack(anchor="w")

        output_frame = ttk.Frame(main)
        output_frame.pack(fill="x", pady=(5, 10))

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
        ).pack(side="left", padx=(8, 0))

        # ----------------------------------------------------
        # BITRATE INFO
        # ----------------------------------------------------

        self.bitrate_info = ttk.Label(
            main,
            text="",
            font=("Segoe UI", 9)
        )

        self.bitrate_info.pack(
            anchor="w",
            pady=(5, 5)
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        ttk.Label(
            main,
            textvariable=self.status
        ).pack(anchor="w")

        ttk.Progressbar(
            main,
            variable=self.progress,
            maximum=100
        ).pack(
            fill="x",
            pady=(5, 15)
        )

        # ----------------------------------------------------
        # EXPORT
        # ----------------------------------------------------

        self.export_button = ttk.Button(
            main,
            text="EXPORT AUDIO",
            command=self.start_export
        )

        self.export_button.pack(
            ipadx=35,
            ipady=8
        )

    # ========================================================
    # GUI UPDATE
    # ========================================================

    def update_format(self):

        if self.format_var.get() == "MP3":

            self.wav_frame.grid_remove()
            self.mp3_frame.grid()

        else:

            self.mp3_frame.grid_remove()
            self.wav_frame.grid()

            self.update_wav_type()

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

    # ========================================================
    # INPUT
    # ========================================================

    def select_input(self):

        filename = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[
                ("Audio files", "*.mp3 *.wav"),
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        self.input_file.set(filename)

        self.update_default_output()

    def update_default_output(self):

        filename = self.input_file.get()

        if not filename:
            return

        base = os.path.splitext(filename)[0]
        extension = self.format_var.get().lower()

        self.output_file.set(
            base + "_export." + extension
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    def select_output(self):

        extension = self.format_var.get().lower()

        filename = filedialog.asksaveasfilename(
            title="Save audio file",
            defaultextension="." + extension,
            filetypes=[
                (
                    extension.upper(),
                    "*." + extension
                )
            ]
        )

        if filename:
            self.output_file.set(filename)

    # ========================================================
    # ADPCM INFO
    # ========================================================

    def update_adpcm_info(self):

        try:
            target = float(
                self.adpcm_target.get()
            )

            channels = 1 if self.wav_channels.get() == "Mono" else 2

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
                    f"Recommended configuration: "
                    f"{rate} Hz / 4 bit / "
                    f"{self.wav_channels.get()}\n"
                    f"Nominal bitrate: "
                    f"{bitrate:.1f} kbps"
                )
            )

        except Exception:

            self.adpcm_info.configure(
                text="Enter a valid target bitrate."
            )

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(self):

        if not os.path.isfile(FFMPEG):

            messagebox.showerror(
                "FFmpeg not found",
                "FFmpeg was not found.\n\n"
                "Place ffmpeg.exe in the following folder:\n\n"
                + FFMPEG_DIR
            )

            return False

        if not os.path.isfile(FFPROBE):

            messagebox.showerror(
                "FFprobe not found",
                "FFprobe was not found.\n\n"
                "Place ffprobe.exe in the following folder:\n\n"
                + FFMPEG_DIR
            )

            return False

        if not self.input_file.get():

            messagebox.showwarning(
                "Missing file",
                "Select an audio file."
            )

            return False

        if not os.path.isfile(
            self.input_file.get()
        ):

            messagebox.showerror(
                "Error",
                "The selected file does not exist."
            )

            return False

        if not self.output_file.get():

            messagebox.showwarning(
                "Missing output",
                "Select the output file."
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
                    "Enter a valid target bitrate."
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
    # COMMAND BUILDING
    # ========================================================

    def build_command(self):

        input_file = self.input_file.get()
        output_file = self.output_file.get()

        command = [
            FFMPEG,
            "-y",
            "-i",
            input_file
        ]

        output_format = self.format_var.get()

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        mode = self.duration_mode.get()

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

            channels = (
                1
                if self.mp3_channels.get() == "Mono"
                else 2
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

            channels = (
                1
                if self.wav_channels.get() == "Mono"
                else 2
            )

            sample_rate = int(
                self.wav_samplerate.get()
            )

            # PCM
            if wav_type.startswith("PCM"):

                command.extend([
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    str(channels),
                    "-c:a",
                    "pcm_s16le"
                ])

            # IMA ADPCM
            else:

                target = float(
                    self.adpcm_target.get()
                )

                # Automatically selects the sample rate
                # closest to the desired bitrate.
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

            # apad adds silence if necessary.
            command.extend([
                "-af",
                f"apad=whole_dur={duration:.3f}",
                "-t",
                f"{duration:.3f}"
            ])

        command.append(output_file)

        return command

    # ========================================================
    # START
    # ========================================================

    def start_export(self):

        if not self.validate():
            return

        self.export_button.configure(
            state="disabled"
        )

        self.progress.set(0)
        self.status.set(
            "Preparing conversion..."
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

        try:

            command = self.build_command()

            # FFmpeg with progressive output.
            command.insert(
                1,
                "-progress"
            )

            command.insert(
                2,
                "pipe:1"
            )

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            total_duration = None

            if self.duration_mode.get() != "keep":

                total_duration = parse_duration(
                    self.duration.get()
                )

            for line in process.stdout:

                line = line.strip()

                if line.startswith("out_time_ms="):

                    try:

                        time_us = int(
                            line.split("=")[1]
                        )

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

                            self.root.after(
                                0,
                                self.progress.set,
                                percentage
                            )

                    except ValueError:
                        pass

                elif line.startswith("progress=end"):

                    self.root.after(
                        0,
                        self.progress.set,
                        100
                    )

            return_code = process.wait()

            if return_code != 0:

                raise RuntimeError(
                    "FFmpeg returned an error."
                )

            # ------------------------------------------------
            # VERIFICATION
            # ------------------------------------------------

            info = self.probe_output()

            self.root.after(
                0,
                self.progress.set,
                100
            )

            self.root.after(
                0,
                self.status.set,
                "Export completed."
            )

            self.root.after(
                0,
                self.show_result,
                info
            )

        except Exception as error:

            self.root.after(
                0,
                self.status.set,
                "Error."
            )

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Error",
                    str(error)
                )
            )

        finally:

            self.root.after(
                0,
                lambda: self.export_button.configure(
                    state="normal"
                )
            )

    # ========================================================
    # FFPROBE
    # ========================================================

    def probe_output(self):

        command = [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of",
            "default=noprint_wrappers=1",
            self.output_file.get()
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        values = {}

        for line in result.stdout.splitlines():

            if "=" in line:

                key, value = line.split(
                    "=",
                    1
                )

                values[key] = value

        duration = values.get(
            "duration"
        )

        bitrate = values.get(
            "bit_rate"
        )

        size = values.get(
            "size"
        )

        try:
            duration = float(duration)
        except Exception:
            duration = None

        try:
            bitrate = int(bitrate) / 1000
        except Exception:
            bitrate = None

        try:
            size = int(size)
        except Exception:
            size = None

        return {
            "duration": duration,
            "bitrate": bitrate,
            "size": size
        }

    # ========================================================
    # RESULT
    # ========================================================

    def show_result(self, info):

        duration_text = format_duration(
            info["duration"]
        )

        if info["bitrate"] is not None:

            bitrate_text = (
                f"{info['bitrate']:.1f} kbps"
            )

        else:

            bitrate_text = "Not available"

        if info["size"] is not None:

            size_mb = info["size"] / 1024 / 1024

            size_text = (
                f"{size_mb:.2f} MB"
            )

        else:

            size_text = "Not available"

        message = (
            "Export completed successfully!\n\n"
            f"Duration: {duration_text}\n"
            f"Effective bitrate: {bitrate_text}\n"
            f"File size: {size_text}\n\n"
            f"File:\n{self.output_file.get()}"
        )

        messagebox.showinfo(
            "Audio exported",
            message
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    try:
        style = ttk.Style()
        style.theme_use("vista")
    except Exception:
        pass

    app = AudioTool(root)

    root.mainloop()
