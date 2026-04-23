#!/usr/bin/env python3
"""
WS2812B UART Sync Controller
Packet format: [0xFF][R1][G1][B1]...[Rn][Gn][Bn][0xFE]
"""

import sys
import json
import math
import serial
import serial.tools.list_ports
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QPushButton, QComboBox, QSlider, QGroupBox,
    QGridLayout, QColorDialog, QScrollArea, QFrame, QFileDialog,
    QStatusBar, QSizePolicy, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import (
    QColor, QPalette, QPainter, QBrush, QLinearGradient,
    QFont, QFontDatabase, QIcon, QPixmap
)

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
START_BYTE = 0xFF
STOP_BYTE  = 0xFE
DEFAULT_LED_COUNT = 8
CONFIG_FILE = "config.txt"

DARK  = "#0d0f14"
MID   = "#161922"
CARD  = "#1e2230"
BORD  = "#2a2f45"
ACCENT= "#00e5ff"
ACCD  = "#007acc"
GREEN = "#00ff88"
WARN  = "#ffaa00"
ERR   = "#ff4455"
TXT   = "#e8ecf4"
TXTS  = "#7a8099"

STYLE = f"""
QMainWindow, QWidget {{
    background-color: {DARK};
    color: {TXT};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {BORD};
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    background-color: {CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QPushButton {{
    background-color: {CARD};
    color: {TXT};
    border: 1px solid {BORD};
    border-radius: 6px;
    padding: 7px 18px;
    font-family: "Consolas", monospace;
}}
QPushButton:hover {{
    background-color: {BORD};
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {ACCD};
    border-color: {ACCENT};
}}
QPushButton#sendBtn {{
    background-color: {ACCD};
    color: #fff;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 28px;
    letter-spacing: 1px;
}}
QPushButton#sendBtn:hover {{
    background-color: {ACCENT};
    color: {DARK};
}}
QPushButton#stopBtn {{
    background-color: #3a1a20;
    color: {ERR};
    border: 1px solid {ERR};
}}
QPushButton#stopBtn:hover {{
    background-color: {ERR};
    color: #fff;
}}
QComboBox {{
    background-color: {CARD};
    color: {TXT};
    border: 1px solid {BORD};
    border-radius: 6px;
    padding: 5px 10px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {MID};
    color: {TXT};
    selection-background-color: {ACCD};
    border: 1px solid {BORD};
}}
QSpinBox {{
    background-color: {CARD};
    color: {TXT};
    border: 1px solid {BORD};
    border-radius: 6px;
    padding: 5px 8px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BORD};
    border-radius: 3px;
    width: 18px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORD};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCD};
    border-radius: 2px;
}}
QScrollArea {{
    background-color: {MID};
    border: 1px solid {BORD};
    border-radius: 6px;
}}
QTabWidget::pane {{
    border: 1px solid {BORD};
    border-radius: 6px;
    background-color: {CARD};
}}
QTabBar::tab {{
    background-color: {MID};
    color: {TXTS};
    border: 1px solid {BORD};
    border-bottom: none;
    padding: 6px 18px;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {CARD};
    color: {ACCENT};
    border-color: {BORD};
}}
QStatusBar {{
    background-color: {MID};
    color: {TXTS};
    border-top: 1px solid {BORD};
    font-size: 11px;
}}
QLabel#headLabel {{
    font-size: 22px;
    font-weight: bold;
    color: {ACCENT};
    letter-spacing: 3px;
}}
QLabel#subLabel {{
    font-size: 11px;
    color: {TXTS};
    letter-spacing: 1px;
}}
"""


# ──────────────────────────────────────────────
# LED Swatch Widget
# ──────────────────────────────────────────────
class LEDSwatch(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, index, color=QColor(255, 0, 0), parent=None):
        super().__init__(parent)
        self.index = index
        self.color = color
        self.setFixedSize(44, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"LED {index + 1} — click to pick color")
        self._glow = 0

    def set_color(self, color: QColor):
        self.color = color
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)
        # glow
        if self.color.value() > 20:
            glow = QColor(self.color)
            glow.setAlpha(60)
            for i in range(4, 0, -1):
                g = self.rect().adjusted(4 - i*2, 4 - i*2, -(4 - i*2), -(4 - i*2))
                p.setPen(Qt.NoPen)
                p.setBrush(glow)
                p.drawEllipse(g)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(self.color))
        p.drawEllipse(r)
        # shine
        shine = QColor(255, 255, 255, 50)
        sr = r.adjusted(4, 4, -r.width()//2, -r.height()//2)
        p.setBrush(QBrush(shine))
        p.drawEllipse(sr)
        # border
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(BORD))
        p.drawEllipse(r)
        # index label
        p.setPen(QColor(TXT))
        p.setFont(QFont("Consolas", 7))
        p.drawText(self.rect(), Qt.AlignBottom | Qt.AlignHCenter,
                   f"{self.index + 1}")


# ──────────────────────────────────────────────
# Packet Visualizer Widget
# ──────────────────────────────────────────────
class PacketVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.packet = []
        self.setMinimumHeight(60)

    def set_packet(self, packet):
        self.packet = packet
        self.update()

    def paintEvent(self, event):
        if not self.packet:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        n = len(self.packet)
        bw = max(10, min(30, w // (n + 1)))
        gap = 2
        total = n * (bw + gap)
        x0 = (w - total) // 2

        for i, byte in enumerate(self.packet):
            x = x0 + i * (bw + gap)
            # color coding
            if i == 0:
                c = QColor(WARN)
            elif i == n - 1:
                c = QColor(ERR)
            else:
                triple_idx = (i - 1) % 3
                led_idx = (i - 1) // 3
                if triple_idx == 0:
                    c = QColor(byte, 0, 0)
                elif triple_idx == 1:
                    c = QColor(0, byte, 0)
                else:
                    c = QColor(0, 0, byte)

            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, h // 2 - 12, bw, 24, 3, 3)

            p.setPen(QColor(TXT))
            p.setFont(QFont("Consolas", 7))
            p.drawText(x, h // 2 + 22, f"{byte:02X}")


# ──────────────────────────────────────────────
# UART Send Thread
# ──────────────────────────────────────────────
class UARTThread(QThread):
    status = pyqtSignal(str, str)   # message, level (ok/err/warn)

    def __init__(self, port, baud, packet):
        super().__init__()
        self.port = port
        self.baud = baud
        self.packet = packet

    def run(self):
        try:
            with serial.Serial(self.port, self.baud, timeout=1) as ser:
                ser.write(bytes(self.packet))
                self.status.emit(
                    f"✓  Sent {len(self.packet)} bytes → {self.port} @ {self.baud} baud",
                    "ok"
                )
        except serial.SerialException as e:
            self.status.emit(f"✗  Serial error: {e}", "err")
        except Exception as e:
            self.status.emit(f"✗  {e}", "err")


# ──────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────
class WS2812BController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WS2812B  ·  UART Sync Controller")
        self.setMinimumSize(860, 680)
        self.resize(980, 760)

        self.led_count = DEFAULT_LED_COUNT
        self.led_colors = [QColor(255, 0, 0)] * self.led_count
        self.swatches: list[LEDSwatch] = []
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._anim_tick)
        self.anim_step = 0
        self.uart_thread = None
        self.continuous_timer = QTimer()
        self.continuous_timer.timeout.connect(self._send_continuous)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._rebuild_led_grid()
        self._refresh_ports()

    # ── UI Construction ────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(18, 14, 18, 14)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("WS2812B")
        title.setObjectName("headLabel")
        sub = QLabel("UART SYNC CONTROLLER  ·  v1.0")
        sub.setObjectName("subLabel")
        sub.setAlignment(Qt.AlignBottom)
        hdr.addWidget(title)
        hdr.addWidget(sub)
        hdr.addStretch()
        # connection indicator dot
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {ERR}; font-size: 18px;")
        self.dot.setToolTip("Connection status")
        hdr.addWidget(self.dot)
        root.addLayout(hdr)

        # Main columns
        cols = QHBoxLayout()
        cols.setSpacing(14)
        root.addLayout(cols)

        # Left panel
        left = QVBoxLayout()
        left.setSpacing(10)
        cols.addLayout(left, 3)

        # ── Port / Baud ──
        port_grp = QGroupBox("SERIAL PORT")
        pg = QGridLayout(port_grp)
        pg.addWidget(QLabel("Port"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(130)
        pg.addWidget(self.port_combo, 0, 1)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.clicked.connect(self._refresh_ports)
        pg.addWidget(refresh_btn, 0, 2)

        pg.addWidget(QLabel("Baud"), 1, 0)
        self.baud_combo = QComboBox()
        for b in [9600, 19200, 38400, 57600, 115200, 250000, 500000, 1000000]:
            self.baud_combo.addItem(str(b), b)
        self.baud_combo.setCurrentText("115200")
        pg.addWidget(self.baud_combo, 1, 1, 1, 2)
        left.addWidget(port_grp)

        # ── LED Count ──
        led_grp = QGroupBox("LED STRIP")
        lg = QGridLayout(led_grp)
        lg.addWidget(QLabel("Count"), 0, 0)
        self.led_spin = QSpinBox()
        self.led_spin.setRange(1, 256)
        self.led_spin.setValue(self.led_count)
        self.led_spin.valueChanged.connect(self._on_led_count_changed)
        lg.addWidget(self.led_spin, 0, 1)

        lg.addWidget(QLabel("Brightness"), 1, 0)
        self.bright_slider = QSlider(Qt.Horizontal)
        self.bright_slider.setRange(1, 100)
        self.bright_slider.setValue(100)
        self.bright_slider.valueChanged.connect(self._apply_brightness_label)
        self.bright_label = QLabel("100%")
        self.bright_label.setStyleSheet(f"color: {ACCENT};")
        lg.addWidget(self.bright_slider, 1, 1)
        lg.addWidget(self.bright_label, 1, 2)
        left.addWidget(led_grp)

        # ── Mode ──
        mode_grp = QGroupBox("EFFECT MODE")
        mg = QGridLayout(mode_grp)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Static", "Breathing", "Rainbow"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mg.addWidget(self.mode_combo, 0, 0, 1, 2)

        mg.addWidget(QLabel("Speed"), 1, 0)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(10, 200)
        self.speed_slider.setValue(60)
        self.speed_label = QLabel("60 ms")
        self.speed_label.setStyleSheet(f"color: {ACCENT};")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"{v} ms"))
        mg.addWidget(self.speed_slider, 1, 1)
        mg.addWidget(self.speed_label, 1, 2)

        # Color picker for static/breathing
        self.color_btn = QPushButton("  Pick Color")
        self.color_btn.clicked.connect(self._pick_global_color)
        self._set_btn_color_preview(self.color_btn, QColor(255, 0, 0))
        mg.addWidget(self.color_btn, 2, 0, 1, 2)
        left.addWidget(mode_grp)

        # ── Send Controls ──
        ctl_grp = QGroupBox("TRANSMIT")
        cg = QVBoxLayout(ctl_grp)
        send_row = QHBoxLayout()
        self.send_btn = QPushButton("▶  SEND ONCE")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.clicked.connect(self._send_once)
        send_row.addWidget(self.send_btn)
        self.stream_btn = QPushButton("⏵  START STREAM")
        self.stream_btn.clicked.connect(self._toggle_stream)
        send_row.addWidget(self.stream_btn)
        cg.addLayout(send_row)

        save_row = QHBoxLayout()
        save_btn = QPushButton("💾  Save Config")
        save_btn.clicked.connect(self._save_config)
        load_btn = QPushButton("📂  Load Config")
        load_btn.clicked.connect(self._load_config)
        save_row.addWidget(save_btn)
        save_row.addWidget(load_btn)
        cg.addLayout(save_row)
        left.addWidget(ctl_grp)

        left.addStretch()

        # Right panel
        right = QVBoxLayout()
        right.setSpacing(10)
        cols.addLayout(right, 5)

        # ── LED Grid ──
        led_grid_grp = QGroupBox("LED PIXELS  —  click to set individual color")
        lgg = QVBoxLayout(led_grid_grp)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(260)
        self.swatch_container = QWidget()
        self.swatch_layout = QGridLayout(self.swatch_container)
        self.swatch_layout.setSpacing(6)
        scroll.setWidget(self.swatch_container)
        lgg.addWidget(scroll)
        right.addWidget(led_grid_grp)

        # ── Packet Preview ──
        pkt_grp = QGroupBox("PACKET PREVIEW")
        pkv = QVBoxLayout(pkt_grp)
        self.pkt_viz = PacketVisualizer()
        pkv.addWidget(self.pkt_viz)
        self.pkt_hex = QLabel("")
        self.pkt_hex.setWordWrap(True)
        self.pkt_hex.setStyleSheet(
            f"color: {TXTS}; font-size: 10px; font-family: Consolas;")
        pkv.addWidget(self.pkt_hex)
        right.addWidget(pkt_grp)

        # ── Log ──
        log_grp = QGroupBox("LOG")
        logv = QVBoxLayout(log_grp)
        self.log_label = QLabel("Waiting for action…")
        self.log_label.setStyleSheet(f"color: {TXTS}; font-size: 11px;")
        self.log_label.setWordWrap(True)
        logv.addWidget(self.log_label)
        right.addWidget(log_grp)
        right.addStretch()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready  ·  Select a port and press SEND")

    # ── LED Grid ──────────────────────────────
    def _rebuild_led_grid(self):
        # clear
        for i in reversed(range(self.swatch_layout.count())):
            w = self.swatch_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.swatches.clear()

        cols = 16
        for i in range(self.led_count):
            s = LEDSwatch(i, self.led_colors[i])
            s.clicked.connect(self._pick_led_color)
            self.swatches.append(s)
            self.swatch_layout.addWidget(s, i // cols, i % cols)

        self._update_packet_preview()

    def _on_led_count_changed(self, v):
        old = self.led_count
        self.led_count = v
        # extend or trim
        if v > old:
            base = self.led_colors[-1] if self.led_colors else QColor(255, 0, 0)
            self.led_colors.extend([QColor(base)] * (v - old))
        else:
            self.led_colors = self.led_colors[:v]
        self._rebuild_led_grid()

    # ── Color Picking ─────────────────────────
    def _pick_led_color(self, idx):
        c = QColorDialog.getColor(self.led_colors[idx], self, f"LED {idx + 1} Color")
        if c.isValid():
            self.led_colors[idx] = c
            self.swatches[idx].set_color(c)
            self._update_packet_preview()

    def _pick_global_color(self):
        c = QColorDialog.getColor(self.led_colors[0], self, "Global Color")
        if c.isValid():
            self._set_btn_color_preview(self.color_btn, c)
            self.led_colors = [QColor(c)] * self.led_count
            for s in self.swatches:
                s.set_color(c)
            self._update_packet_preview()

    def _set_btn_color_preview(self, btn, color: QColor):
        r, g, b = color.red(), color.green(), color.blue()
        btn.setStyleSheet(
            f"QPushButton {{ background: rgb({r},{g},{b}); "
            f"color: {'#000' if color.lightness() > 128 else '#fff'}; "
            f"border: 1px solid {BORD}; border-radius: 6px; padding: 7px 18px; }}"
        )

    # ── Mode ──────────────────────────────────
    def _on_mode_changed(self, mode):
        is_static = mode == "Static"
        self.color_btn.setVisible(mode in ("Static", "Breathing"))
        if mode == "Rainbow":
            self._apply_rainbow(0)
        elif mode == "Static":
            self.anim_timer.stop()
        elif mode == "Breathing":
            pass  # handled in stream

    def _apply_brightness_label(self, v):
        self.bright_label.setText(f"{v}%")
        self._update_packet_preview()

    # ── Packet Building ───────────────────────
    def _build_packet(self, colors=None):
        if colors is None:
            colors = self.led_colors
        bright = self.bright_slider.value() / 100.0
        packet = [START_BYTE]
        for c in colors:
            packet.append(int(c.red()   * bright) & 0xFF)
            packet.append(int(c.green() * bright) & 0xFF)
            packet.append(int(c.blue()  * bright) & 0xFF)
        packet.append(STOP_BYTE)
        return packet

    def _update_packet_preview(self):
        pkt = self._build_packet()
        self.pkt_viz.set_packet(pkt)
        hex_str = " ".join(f"{b:02X}" for b in pkt)
        # show first 80 bytes in hex label
        display = hex_str if len(hex_str) <= 200 else hex_str[:200] + " …"
        self.pkt_hex.setText(display)

    # ── Animation ─────────────────────────────
    def _apply_rainbow(self, step):
        n = self.led_count
        for i, s in enumerate(self.swatches):
            hue = int((i / max(n, 1) * 360 + step) % 360)
            c = QColor.fromHsv(hue, 255, 255)
            self.led_colors[i] = c
            s.set_color(c)
        self._update_packet_preview()

    def _anim_tick(self):
        mode = self.mode_combo.currentText()
        self.anim_step += 1
        if mode == "Rainbow":
            self._apply_rainbow(self.anim_step * 5)
        elif mode == "Breathing":
            angle = (self.anim_step * 0.05) % (2 * math.pi)
            factor = (math.sin(angle) + 1) / 2
            base = self.led_colors[0] if self.led_colors else QColor(255, 0, 0)
            r = int(base.red()   * factor)
            g = int(base.green() * factor)
            b = int(base.blue()  * factor)
            bc = QColor(r, g, b)
            for s in self.swatches:
                s.set_color(bc)
            self._update_packet_preview()

    # ── Send ──────────────────────────────────
    def _get_port_baud(self):
        port = self.port_combo.currentText()
        baud = self.baud_combo.currentData()
        if not port:
            self._log("No port selected", "warn")
            return None, None
        return port, baud

    def _send_once(self):
        port, baud = self._get_port_baud()
        if not port:
            return
        pkt = self._build_packet()
        self.uart_thread = UARTThread(port, baud, pkt)
        self.uart_thread.status.connect(self._on_uart_status)
        self.uart_thread.start()

    def _toggle_stream(self):
        if self.continuous_timer.isActive():
            self.continuous_timer.stop()
            self.anim_timer.stop()
            self.stream_btn.setText("⏵  START STREAM")
            self.stream_btn.setObjectName("")
            self.stream_btn.setStyleSheet("")
            self._log("Stream stopped", "warn")
        else:
            port, baud = self._get_port_baud()
            if not port:
                return
            interval = self.speed_slider.value()
            self.anim_timer.start(interval)
            self.continuous_timer.start(interval)
            self.stream_btn.setText("⏹  STOP STREAM")
            self.stream_btn.setObjectName("stopBtn")
            self.stream_btn.setStyleSheet(
                f"background-color: #3a1a20; color: {ERR}; "
                f"border: 1px solid {ERR}; border-radius: 6px; padding: 7px 18px;")
            self._log(f"Streaming → {port} @ {baud} baud", "ok")

    def _send_continuous(self):
        port, baud = self._get_port_baud()
        if not port:
            return
        pkt = self._build_packet()
        try:
            if not hasattr(self, '_ser') or not self._ser.is_open:
                self._ser = serial.Serial(port, baud, timeout=0.1)
            self._ser.write(bytes(pkt))
        except Exception as e:
            self._log(f"Stream error: {e}", "err")
            self.continuous_timer.stop()
            self.anim_timer.stop()

    def _on_uart_status(self, msg, level):
        self._log(msg, level)

    def _log(self, msg, level="ok"):
        colors = {"ok": GREEN, "warn": WARN, "err": ERR}
        c = colors.get(level, TXT)
        self.log_label.setText(f'<span style="color:{c}">{msg}</span>')
        self.status_bar.showMessage(msg)
        if level == "ok":
            self.dot.setStyleSheet(f"color: {GREEN}; font-size: 18px;")
        elif level == "err":
            self.dot.setStyleSheet(f"color: {ERR}; font-size: 18px;")

    # ── Ports ─────────────────────────────────
    def _refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
        if not ports:
            self.port_combo.addItem("(no ports found)")
            self._log("No serial ports detected", "warn")
        else:
            self._log(f"Found {len(ports)} port(s)", "ok")

    # ── Config Save / Load ────────────────────
    def _save_config(self):
        cfg = {
            "led_count": self.led_count,
            "baud": self.baud_combo.currentData(),
            "port": self.port_combo.currentText(),
            "mode": self.mode_combo.currentText(),
            "brightness": self.bright_slider.value(),
            "speed": self.speed_slider.value(),
            "colors": [
                [c.red(), c.green(), c.blue()] for c in self.led_colors
            ]
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", CONFIG_FILE, "Config Files (*.txt *.json)")
        if not path:
            return
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        self._log(f"Config saved → {path}", "ok")

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "", "Config Files (*.txt *.json)")
        if not path:
            return
        try:
            with open(path) as f:
                cfg = json.load(f)
            self.led_spin.setValue(cfg.get("led_count", 8))
            idx = self.baud_combo.findData(cfg.get("baud", 115200))
            if idx >= 0:
                self.baud_combo.setCurrentIndex(idx)
            idx2 = self.port_combo.findText(cfg.get("port", ""))
            if idx2 >= 0:
                self.port_combo.setCurrentIndex(idx2)
            self.mode_combo.setCurrentText(cfg.get("mode", "Static"))
            self.bright_slider.setValue(cfg.get("brightness", 100))
            self.speed_slider.setValue(cfg.get("speed", 60))
            colors = cfg.get("colors", [])
            for i, rgb in enumerate(colors[:self.led_count]):
                self.led_colors[i] = QColor(*rgb)
                if i < len(self.swatches):
                    self.swatches[i].set_color(self.led_colors[i])
            self._update_packet_preview()
            self._log(f"Config loaded ← {path}", "ok")
        except Exception as e:
            self._log(f"Load failed: {e}", "err")

    def closeEvent(self, event):
        self.anim_timer.stop()
        self.continuous_timer.stop()
        if hasattr(self, '_ser') and self._ser.is_open:
            self._ser.close()
        event.accept()


# ──────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = WS2812BController()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
