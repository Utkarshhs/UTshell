# UT Shell 

A custom, lightweight, and modern Linux desktop shell built from scratch with **Python**, **GTK3 (`PyGObject`)**, and **Fabric** for the **Wayfire** Wayland compositor on **Fedora Linux**.

Inspired by **Ax-Shell**, **Caelestia**, and **Noctalia**, UT Shell features a floating **3-Island Split Top Bar**, custom dark obsidian glassmorphic CSS styling (`styles/style.css`), and interactive system control popups.

## Features

* **3-Island Floating Top Bar**:

  * **Left Island**: App Launcher menu trigger (`Gio.AppInfo` live search), up to 3 active Wayfire windows (displaying both app icon and window title), and a dynamic `+N` / **All** overflow button (`AppsPopup`) to view and focus any open window.

  * **Middle Island**: Clickable cursive user pill (`Utkarsh`) that toggles the main Control Center drop-down.

  * **Right Island**: Live battery status badge and date/clock pill that toggles a custom-styled dark GTK Calendar popup.

* **Interactive Popups & Widgets**:

  * **Control Center (`ControlCenterPopup`)**: Hardware quick-toggles (Wi-Fi, Bluetooth Manager, Display, Airplane Mode, Notifications, Night Light, Mic Mute, and Trash), live PipeWire/WirePlumber (`wpctl`) speaker & microphone sliders, expandable live weather banner (`wttr.in`), and real-time CPU, Temperature, RAM, and Disk sensors.

  * **Application Launcher (`AppLauncherPopup`)**: Searchable app drawer for all installed desktop applications powered by `Gio.AppInfo`.

  * **Window Switcher (`AppsPopup`)**: Live list of open Wayfire toplevel views retrieved via the Wayfire IPC socket.

  * **Calendar (`calendarpopup`)**: Custom dark-glass `Gtk.Calendar` popup widget.

## Prerequisites & Dependencies

### 1. System Packages

#### **Fedora Linux**

Install the required GTK3, Layer Shell, GObject Introspection, and hardware control utilities via `dnf`:

```
sudo dnf install -y \
    python3-devel \
    python3-pip \
    python3-gobject \
    gtk3-devel \
    gtk-layer-shell-devel \
    gobject-introspection-devel \
    cairo-devel \
    cairo-gobject-devel \
    pkgconf-pkg-config \
    wireplumber \
    NetworkManager \
    bluez \
    blueman \
    util-linux \
    gnome-control-center \
    wlsunset \
    curl \
    jetbrains-mono-fonts-all

```

#### **Arch Linux**

```
sudo pacman -S python-pip python-gobject gtk3 gtk-layer-shell \
    gobject-introspection wireplumber networkmanager bluez-utils \
    blueman gnome-control-center wlsunset curl ttf-jetbrains-mono-nerd

```

### 2. Python Libraries

UT Shell requires `PyGObject`, `pywayfire` (for communicating with Wayfire's IPC socket), `loguru`, and `Fabric`:

```
pip install --upgrade PyGObject pywayfire loguru
pip install "git+https://github.com/Fabric-Development/fabric.git"

```

## Wayfire Configuration

UT Shell relies on Wayfire's IPC plugins to query and switch focused windows.

1. Open your Wayfire configuration file: `~/.config/wayfire.ini`

2. Ensure the `ipc` and `ipc-rules` plugins are included in your active plugins list:

```
[core]
plugins = alpha autostart command fast-switcher grid idle move place resize switcher wayfire-shell ipc ipc-rules

```

## Installation & Usage

1. **Clone the repository**:

   ```
   git clone https://github.com/<your-github-username>/utshell.git
   cd utshell
   
   ```

2. **Run UT Shell**:

   ```
   python3 main.py
   
   ```

3. **Autostart in Wayfire (Optional)**:
   Add UT Shell to the `[autostart]` section of `~/.config/wayfire.ini` so it runs automatically when Wayfire launches:

   ```
   [autostart]
   utshell = python3 /path/to/utshell/main.py
   
   ```

## Project Structure

```
utshell/
├── main.py            # Core shell windows, Wayfire IPC integration, Fabricators & popups
├── styles/
│   └── style.css      # Zero-warning GTK3 CSS theme (3-island bar, glass popups, pill sliders)
└── README.md          # Documentation & setup guide

```

## Notes & Troubleshooting

* **GNOME Control Center under Wayfire**:
  `gnome-control-center` panels are invoked with `env XDG_CURRENT_DESKTOP=GNOME` so they open cleanly outside a standard GNOME desktop session.

* **PyGObject 3.51+ / 3.58+ Compatibility Fix**:
  If running on newer PyGObject versions before Fabric's `gtk-layer-shell` enum patch is merged upstream, install the patched branch:

  ```
  pip install --no-deps --force-reinstall "git+https://github.com/Awareness10/fabric.git@fix/gtype-less-enum-properties"
  
  ```

* **GitHub Language Stats Cleanup**:
  If you have `.ipynb` notebook files in your repo that inflate Jupyter Notebook stats on GitHub, add a `.gitattributes` file in the root directory:

  ```
  *.ipynb linguist-vendored=true
  
  ```