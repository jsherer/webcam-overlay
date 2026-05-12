# webcam overlay

A simple, no-chrome utility that displays a small borderless webcam image on your desktop. Built for screen recordings — sits as a circular bubble in a screen corner, always on top, draggable.

## Install

```
pip install -r requirements.txt
```

On Debian/Ubuntu you may also need:

```
sudo apt install python3-tk libxcb-cursor0
```

## Run

```
python3 webcam_overlay.py
```

Defaults: 200px circle, bottom-right corner, 40px from the screen edges, first camera, mirrored.

### Options

| Flag | Default | Description |
|---|---|---|
| `--size N` | 200 | Diameter in pixels |
| `--offset N` | 40 | Distance from the screen edge in pixels |
| `--position {tl,tr,bl,br}` | `br` | Starting corner |
| `--camera N` | first available | Initial camera index |
| `--no-mirror` | mirror on | Disable the selfie-style horizontal flip |
| `--fps N` | 33 | Frame rate |
| `--hidpi` | off | Render the bubble at the display's device pixel ratio for sharper output on HiDPI screens |

Examples:

```
python3 webcam_overlay.py --size 280 --offset 20
python3 webcam_overlay.py --position tl --no-mirror
python3 webcam_overlay.py --camera 2 --fps 60
```

## Interaction

- **Left-click and drag** — move the bubble
- **Right-click** — menu: switch camera / toggle mirror / exit

## Notes

- Forces the Qt `xcb` (X11/Xwayland) platform by default so window positioning works under GNOME/Mutter, which refuses client-side positioning on native Wayland. Override with `QT_QPA_PLATFORM=wayland` if you need native Wayland and don't mind losing positioning.
- The 40px offset is measured from the physical screen edge, so the bubble may sit behind a bottom dock if you have one — drag it where you want it.
