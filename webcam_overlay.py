#!/home/jordan/Development/jsherer/experiment-webcam-overlay/env/bin/python3
"""Borderless, always-on-top circular webcam overlay.

PyQt6-based. Per-pixel alpha gives a true circular bubble on X11 and Wayland.
Left-drag to move. Right-click for menu (switch camera / toggle mirror / exit).
"""

import argparse
import contextlib
import os
import sys

# Force Qt onto Xwayland so we can position the window. Wayland compositors
# (notably GNOME Mutter) refuse client-side positioning.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
from PyQt6.QtCore import Qt, QPoint, QTimer, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPainterPath, QAction
from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QMessageBox


SIZE = 224
FRAME_INTERVAL_MS = 30
MAX_CAMERA_PROBE = 6
EDGE_OFFSET = 40
CORNERS = ("tl", "tr", "bl", "br")


@contextlib.contextmanager
def _suppress_fd_stderr():
    # OpenCV's C++ layer writes to fd 2 directly; redirect it at the OS level.
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(devnull)
        os.close(saved)


def enumerate_cameras():
    found = []
    with _suppress_fd_stderr():
        for i in range(MAX_CAMERA_PROBE):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(i)
            cap.release()
    return found


class WebcamOverlay(QWidget):
    def __init__(self, cameras, size=SIZE, mirror=True, camera=0, fps=33, hidpi=False):
        super().__init__()
        self.size_px = size
        self.cameras = cameras
        self.cam_index = cameras.index(camera) if camera in cameras else 0
        self.cap = cv2.VideoCapture(self.cameras[self.cam_index])
        self.mirror = mirror
        self.hidpi = hidpi
        self.pixmap = None
        self._drag_pos = None
        interval_ms = max(1, int(1000 / fps))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.size_px, self.size_px)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(interval_ms)

    def _update_frame(self):
        ok, frame = self.cap.read()
        if not ok:
            return
        if self.mirror:
            frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        s = min(h, w)
        y0 = (h - s) // 2
        x0 = (w - s) // 2
        frame = frame[y0:y0 + s, x0:x0 + s]
        dpr = self.devicePixelRatioF() if self.hidpi else 1.0
        target = max(1, int(round(self.size_px * dpr)))
        frame = cv2.resize(frame, (target, target))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(
            rgb.data, target, target,
            rgb.strides[0], QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(qimg)
        if self.hidpi:
            pixmap.setDevicePixelRatio(dpr)
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, _event):
        if self.pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, self.size_px, self.size_px))
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, _event):
        self._drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        switch_action = QAction("Switch camera", self)
        switch_action.triggered.connect(self._switch_camera)
        switch_action.setEnabled(len(self.cameras) > 1)
        menu.addAction(switch_action)

        mirror_action = QAction("Toggle mirror", self)
        mirror_action.triggered.connect(self._toggle_mirror)
        menu.addAction(mirror_action)

        menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)

        menu.exec(event.globalPos())

    def _switch_camera(self):
        if len(self.cameras) < 2:
            return
        self.cap.release()
        self.cam_index = (self.cam_index + 1) % len(self.cameras)
        self.cap = cv2.VideoCapture(self.cameras[self.cam_index])

    def _toggle_mirror(self):
        self.mirror = not self.mirror

    def cleanup(self):
        self.timer.stop()
        try:
            self.cap.release()
        except Exception:
            pass

    def closeEvent(self, event):
        self.cleanup()
        event.accept()


def _corner_pos(screen, size, offset, corner):
    if corner == "tl":
        return offset, offset
    if corner == "tr":
        return screen.right() - size - offset + 1, offset
    if corner == "bl":
        return offset, screen.bottom() - size - offset + 1
    return screen.right() - size - offset + 1, screen.bottom() - size - offset + 1


def parse_args(argv):
    p = argparse.ArgumentParser(description="Circular webcam overlay")
    p.add_argument("--size", type=int, default=SIZE, help="diameter in px (default: %(default)s)")
    p.add_argument("--offset", type=int, default=EDGE_OFFSET, help="px from screen edge (default: %(default)s)")
    p.add_argument("--position", choices=CORNERS, default="br", help="starting corner (default: %(default)s)")
    p.add_argument("--camera", type=int, default=2, help="initial camera index (default: first available)")
    p.add_argument("--no-mirror", action="store_true", help="start with mirroring off")
    p.add_argument("--fps", type=int, default=33, help="frame rate (default: %(default)s)")
    p.add_argument("--hidpi", action="store_true", help="render at device pixel ratio for HiDPI displays")
    return p.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    app = QApplication(sys.argv)
    cameras = enumerate_cameras()
    if not cameras:
        QMessageBox.critical(None, "Webcam overlay", "No cameras detected.")
        sys.exit(1)
    overlay = WebcamOverlay(
        cameras,
        size=args.size,
        mirror=not args.no_mirror,
        camera=args.camera if args.camera is not None else cameras[0],
        fps=args.fps,
        hidpi=args.hidpi,
    )
    app.aboutToQuit.connect(overlay.cleanup)
    screen = app.primaryScreen().geometry()
    x, y = _corner_pos(screen, args.size, args.offset, args.position)
    overlay.move(x, y)
    overlay.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
