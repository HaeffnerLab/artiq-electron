import time
from PyQt5 import QtWidgets, QtCore, QtGui
from artiq.applets.simple import SimpleApplet

# Import the required beep function
try:
    from edes.utils.utils import beep_python
except ImportError:
    def beep_python():
        print("Beep!")


class ProgressBarWidget(QtWidgets.QWidget):
    def __init__(self, args):
        super().__init__()
        self.dataset_name = args.dataset

        # Tracking state for elapsed time, speed, ETA, and sound playback
        self.start_time = None
        self.last_current = None
        self.last_time = None
        self.speed = 0.0  # items per second
        self.has_beeped = False  # Ensure beep triggers only once per completion

        # Set background to solid white
        self.setStyleSheet("background-color: white;")

        # Main Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Sub-font for metrics and controls
        sub_font = QtGui.QFont()
        sub_font.setPointSize(max(8, args.font_size - 4))

        # Checkbox selection placed at the top-left corner
        self.beep_checkbox = QtWidgets.QCheckBox("Beep when completed", self)
        self.beep_checkbox.setFont(sub_font)
        self.beep_checkbox.setStyleSheet("color: #333333; margin-bottom: 5px;")
        layout.addWidget(self.beep_checkbox, alignment=QtCore.Qt.AlignLeft)

        # Label font setup (larger size)
        font = QtGui.QFont()
        font.setPointSize(args.font_size)
        font.setBold(True)

        # Main progress info label (e.g. "50/100 [50%]")
        self.info_label = QtWidgets.QLabel("0/0 [0%]", self)
        self.info_label.setFont(font)
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #333333;")
        layout.addWidget(self.info_label)

        # Progress bar setup
        self.pbar = QtWidgets.QProgressBar(self)
        self.pbar.setAlignment(QtCore.Qt.AlignCenter)
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        
        # Style progress bar to match the larger font and custom theme
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                font-size: {args.font_size}pt;
                font-weight: bold;
                background-color: #f0f0f0;
                height: 35px;
            }}
            QProgressBar::chunk {{
                background-color: #007acc;
                width: 10px;
            }}
        """)
        layout.addWidget(self.pbar)

        # Secondary label for tqdm metrics (Elapsed, ETA, & Speed)
        self.metrics_label = QtWidgets.QLabel("Elapsed: 00:00:00 | ETA: --:--:-- | Speed: -- it/s", self)
        self.metrics_label.setFont(sub_font)
        self.metrics_label.setAlignment(QtCore.Qt.AlignCenter)
        self.metrics_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.metrics_label)

    def _format_time(self, seconds):
        """Helper to format seconds strictly into HH:MM:SS."""
        seconds = int(seconds)
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}"

    def data_changed(self, data, mods):
        try:
            # Extract [current_index, total_items] from ARTIQ dataset payload
            raw_current, total = data[self.dataset_name][1]
            raw_current = int(raw_current)
            total = int(total)

            now = time.time()

            # Reset timer and state when progress drops to 0 or resets backward
            if raw_current == 0 or (self.last_current is not None and raw_current < self.last_current):
                self.start_time = now if raw_current > 0 else None
                self.speed = 0.0
                self.has_beeped = False  # Reset beep status for the new run
            elif self.start_time is None and raw_current > 0:
                self.start_time = now

            # Calculate total elapsed time
            elapsed_seconds = (now - self.start_time) if self.start_time is not None else 0
            elapsed_str = self._format_time(elapsed_seconds)

            # Calculate speed using exponential moving average based on index steps
            if self.last_time is not None and self.last_current is not None and raw_current > self.last_current:
                dt = now - self.last_time
                dn = raw_current - self.last_current

                if dt > 0 and dn > 0:
                    inst_speed = dn / dt
                    self.speed = inst_speed if self.speed == 0.0 else (0.7 * self.speed + 0.3 * inst_speed)

            self.last_time = now
            self.last_current = raw_current

            if total > 0:
                # Convert 0-indexed loop counter to 1-indexed item count for UI display
                # If dataset sends raw_current == total, clip to total
                completed_count = min(raw_current, total) if raw_current < total else total

                pct = int((completed_count / total) * 100)
                pct = max(0, min(100, pct))

                # Update progress bar and text in complete synchronization
                self.info_label.setText(f"{completed_count}/{total} [{pct}%]")
                self.pbar.setMaximum(total)
                self.pbar.setValue(completed_count)
                

                # ETA calculation
                remaining = total - completed_count
                if self.speed > 0 and remaining > 0:
                    eta_str = self._format_time(remaining / self.speed)
                    speed_str = f"{self.speed:.2f} it/s"
                elif remaining == 0:
                    eta_str = "00:00:00"
                    speed_str = f"{self.speed:.2f} it/s" if self.speed > 0 else "-- it/s"
                else:
                    eta_str = "--:--:--"
                    speed_str = "-- it/s"

                self.metrics_label.setText(
                    f"Elapsed: {elapsed_str} | ETA: {eta_str} | Speed: {speed_str}"
                )

                # Check for completion (100%) and trigger beep
                if completed_count >= total and not self.has_beeped:
                    if self.beep_checkbox.isChecked():
                        beep_python()
                    self.has_beeped = True  # Prevent repeated beep triggers
            else:
                self.pbar.setValue(0)
                self.info_label.setText("0/0 [0%]")
                self.metrics_label.setText("Elapsed: 00:00:00 | ETA: --:--:-- | Speed: -- it/s")

        except (KeyError, ValueError, TypeError, IndexError):
            self.pbar.setValue(0)
            self.info_label.setText("---/--- [---%]")
            self.metrics_label.setText("Elapsed: --:--:-- | ETA: --:--:-- | Speed: -- it/s")


def main():
    applet = SimpleApplet(ProgressBarWidget)
    applet.add_dataset("dataset", "dataset to show (2-element array: [current, total])")
    
    applet.argparser.add_argument(
        "--font-size", type=int, default=14, help="font size for progress text"
    )
    applet.run()


if __name__ == "__main__":
    main()