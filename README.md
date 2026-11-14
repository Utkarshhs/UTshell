# UT Shell

A custom Linux desktop shell built from scratch with **Python**, **GTK3 (`PyGObject`)**, and **Fabric** for **Wayfire** on **Fedora Linux**. Designed around a 3-island floating split bar, custom glassmorphic CSS styling (`styles/style.css`), and interactive popup panels.

## Features

- **3-Island Split Top Bar**:
  - **Left Island**: Application launcher trigger, up to 3 active windows (with icon and title), and a `+N` / **All** overflow popup (`AppsPopup`) to focus any open window.
  - **Middle Island**: Clickable cursive user badge (`Utkarsh`) that toggles the Control Center popup.
  - **Right Island**: Live system status/battery indicator and date/clock pill that toggles a dark-themed calendar popup.
- **Interactive Popups**:
  - **App Launcher (`AppLauncherPopup`)**: Searchable application menu powered by `Gio.AppInfo`.
  - **All Open Windows (`AppsPopup`)**: Lists active Wayfire toplevel views and focuses them on click.
  - **Control Center (`ControlCenterPopup`)**: Quick hardware settings (`gnome-control-center` with `XDG_CURRENT_DESKTOP=GNOME`), PipeWire/WirePlumber audio controls (`wpctl`), weather display, and system stats.
  - **Calendar (`calendarpopup`)**: Custom-styled `Gtk.Calendar` popup.

## Environment & Dependencies

- **OS**: Fedora Linux
- **Compositor**: Wayfire (Wayland with `gtk-layer-shell`)
- **Runtime**: Python 3.14+ with `PyGObject` (3.51+ / 3.58+) and `gtk3`
- **Framework**: [Fabric](https://github.com/Fabric-Development/fabric)
- **System Utilities**: `wpctl` (WirePlumber), `rfkill`, `bluetoothctl`, `nmcli`, and `gnome-control-center`

## Installation & Running

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url> utshell
   cd utshell
