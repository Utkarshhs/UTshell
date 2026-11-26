import os
import time
import subprocess
import threading
import gi
import math
from datetime import datetime
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk, GLib, Gio
from fabric import Application, Fabricator
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.revealer import Revealer
from wayfire import WayfireSocket



class DismissiblePopup(Window):
    _instances = []
    def __init__(
        self,
        name="dismissible-popup",
        anchor="top bottom left right",
        halign=Gtk.Align.CENTER,
        visible=False,
        top_margin=48,
        side_margin=16,
        layer="overlay",
        **kwargs,
    ):
        super().__init__(
            name=name,
            layer=layer,
            anchor=anchor,
            exclusivity="none",
            keyboard_mode="on-demand",
            visible=visible,
            style_classes=["dismiss-backdrop"],
            **kwargs,
        )
        DismissiblePopup._instances.append(self)

        self.backdrop = Gtk.EventBox()
        self.backdrop.set_visible_window(True)
        self.backdrop.connect("button-press-event", self._on_backdrop_click)

        self.card = Box(
            orientation="v",
            spacing=12,
            style_classes=["popup-card"],
        )
        self.card.set_halign(halign)
        self.card.set_valign(Gtk.Align.START)
        self.card.set_margin_top(top_margin)
        if halign == Gtk.Align.START:
            self.card.set_margin_start(side_margin)
        elif halign == Gtk.Align.END:
            self.card.set_margin_end(side_margin)

        self.backdrop.add(self.card)
        self.add(self.backdrop)

        self.connect("key-press-event", self._on_key_press)

    def _on_backdrop_click(self, widget, event):
        coords = self.card.translate_coordinates(widget, 0, 0)
        if coords is not None:
            cx, cy = coords
            alloc = self.card.get_allocation()
            inside = (cx <= event.x <= cx + alloc.width) and (cy <= event.y <= cy + alloc.height)
            if not inside:
                self.set_visible(False)
                return True
        return False

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        return False

    def toggle(self):
        if self.get_visible():
            self.set_visible(False)
        else:
            self.show_all()
            self.set_visible(True)

    @classmethod
    def close_all(cls, exclude=None):
        for win in cls._instances:
            if win is not exclude and win.get_visible():
                win.set_visible(False)

    def _on_backdrop_click(self, widget, event):
        coords = self.card.translate_coordinates(widget, 0, 0)
        if coords is not None:
            cx, cy = coords
            alloc = self.card.get_allocation()
            inside = (cx <= event.x <= cx + alloc.width) and (cy <= event.y <= cy + alloc.height)
            if not inside:
                DismissiblePopup.close_all()
                return True
        return False

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            DismissiblePopup.close_all()
            return True
        return False

    def toggle(self):
        if self.get_visible():
            self.set_visible(False)
        else:
            DismissiblePopup.close_all(exclude=self)
            self.show_all()
            self.set_visible(True)

class AnimatedClockPopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(
            name="clock-popup",
            halign=Gtk.Align.CENTER,  # Opens centered under the clock island
            top_margin=48,
            **kwargs
        )
        self._timer_id = None

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(240, 240)
        self.canvas.connect("draw", self._on_draw)

        self.digital_time = Label(label=time.strftime("%I:%M:%S %p"), style_classes=["popup-title"])
        self.digital_date = Label(label=time.strftime("%A, %B %d, %Y"), style_classes=["muted-text"])

        self.card.add(self.canvas)
        self.card.add(self.digital_time)
        self.card.add(self.digital_date)

        # Pause animation when hidden so it uses zero CPU when closed
        self.connect("hide", self._stop_animation)

    def toggle(self):
        super().toggle()
        if self.get_visible():
            self._start_animation()
        else:
            self._stop_animation()

    def _start_animation(self):
        if self._timer_id is None:
            self._timer_id = GLib.timeout_add(33, self._tick)  # ~30 FPS smooth sweep

    def _stop_animation(self, *_):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _tick(self):
        if not self.get_visible():
            self._timer_id = None
            return False
        now = datetime.now()
        self.digital_time.set_label(now.strftime("%I:%M:%S %p"))
        self.digital_date.set_label(now.strftime("%A, %B %d, %Y"))
        self.canvas.queue_draw()
        return True

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        cx, cy = alloc.width / 2, alloc.height / 2
        radius = min(cx, cy) - 14

        now = datetime.now()
        sec = now.second + now.microsecond / 1_000_000.0
        minute = now.minute + sec / 60.0
        hour = (now.hour % 12) + minute / 60.0

        # Dial background
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.set_source_rgba(0.11, 0.11, 0.18, 0.9)
        cr.fill_preserve()
        cr.set_source_rgba(0.80, 0.65, 0.97, 0.25)
        cr.set_line_width(2)
        cr.stroke()

        # Animated sweeping seconds progress ring
        start_angle = -math.pi / 2
        sec_angle = start_angle + (sec / 60.0) * 2 * math.pi
        cr.set_source_rgba(0.80, 0.65, 0.97, 0.85)
        cr.set_line_width(3.5)
        cr.arc(cx, cy, radius - 5, start_angle, sec_angle)
        cr.stroke()

        # Hour & minute tick marks
        for i in range(60):
            angle = start_angle + (i / 60.0) * 2 * math.pi
            is_hour = (i % 5 == 0)
            inner = radius - (18 if is_hour else 12)
            outer = radius - 8
            cr.set_source_rgba(0.80, 0.84, 0.96, 0.85 if is_hour else 0.25)
            cr.set_line_width(2.2 if is_hour else 1.0)
            cr.move_to(cx + inner * math.cos(angle), cy + inner * math.sin(angle))
            cr.line_to(cx + outer * math.cos(angle), cy + outer * math.sin(angle))
            cr.stroke()

        # Helper for rounded clock hands
        cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND

        # Hour hand
        hr_angle = start_angle + (hour / 12.0) * 2 * math.pi
        cr.set_source_rgba(0.80, 0.84, 0.96, 1.0)
        cr.set_line_width(5)
        cr.move_to(cx, cy)
        cr.line_to(cx + radius * 0.50 * math.cos(hr_angle), cy + radius * 0.50 * math.sin(hr_angle))
        cr.stroke()

        # Minute hand
        min_angle = start_angle + (minute / 60.0) * 2 * math.pi
        cr.set_source_rgba(0.54, 0.71, 0.98, 1.0)
        cr.set_line_width(3.5)
        cr.move_to(cx, cy)
        cr.line_to(cx + radius * 0.72 * math.cos(min_angle), cy + radius * 0.72 * math.sin(min_angle))
        cr.stroke()

        # Smooth sweeping second hand
        cr.set_source_rgba(0.80, 0.65, 0.97, 1.0)
        cr.set_line_width(2)
        cr.move_to(cx - radius * 0.16 * math.cos(sec_angle), cy - radius * 0.16 * math.sin(sec_angle))
        cr.line_to(cx + radius * 0.82 * math.cos(sec_angle), cy + radius * 0.82 * math.sin(sec_angle))
        cr.stroke()

        # Center cap
        cr.arc(cx, cy, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(0.80, 0.65, 0.97, 1.0)
        cr.fill()

def get_wayfire():
    try:
        sock = WayfireSocket(allow_manual_search=True)
        views = sock.list_views()
        theme = Gtk.IconTheme.get_default()

        app_list = []
        for view in views:
            if view.get("role") == "toplevel" and view.get("mapped") is True:
                app_name = view.get("app-id")
                view_id = view.get("id")
                title = view.get("title", app_name)

                if app_name:
                    if "brave-" in app_name and len(app_name) > 15:
                        clean_words = "".join([c if c.isalnum() else " " for c in title]).lower().split()
                        app_name = "brave-browser"
                        for word in clean_words:
                            if theme.has_icon(word):
                                app_name = word
                                break

                    if not theme.has_icon(app_name):
                        if "kitty" in app_name.lower():
                            app_name = "utilities-terminal"
                        elif "code" in app_name.lower():
                            app_name = (
                                "com.visualstudio.code"
                                if theme.has_icon("com.visualstudio.code")
                                else "text-editor"
                            )
                        else:
                            app_name = "application-x-executable"

                    app_list.append({"id": view_id, "app_id": app_name, "title": title})
        return app_list
    except Exception as e:
        print(f"IPC Error: {e}")
        return []


def focus_window(view_id):
    try:
        sock = WayfireSocket(allow_manual_search=True)
        if hasattr(sock, "set_focus"):
            sock.set_focus(view_id)
        else:
            print("Focus method missing. Check your pywayfire library.")
    except Exception as e:
        print(f"Focus Error: {e}")


def get_audio_output_info():
    """Returns (icon_name, label_text) for the current default audio output."""
    try:
        wp_info = subprocess.check_output(
            ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).lower()
    except Exception:
        wp_info = ""

    active_port = ""
    try:
        default_sink = subprocess.check_output(
            ["pactl", "get-default-sink"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        sinks_out = subprocess.check_output(
            ["pactl", "list", "sinks"], text=True, stderr=subprocess.DEVNULL
        )
        in_sink = False
        for line in sinks_out.splitlines():
            if f"Name: {default_sink}" in line:
                in_sink = True
            elif in_sink and "Active Port:" in line:
                active_port = line.lower()
                break
    except Exception:
        pass

    combined = wp_info + " " + active_port

    if any(k in combined for k in ["headset", "handsfree", "hfp", "hsp"]):
        return ("audio-headset-symbolic", "Headset")
    if any(k in combined for k in ["headphone", "earbud", "buds", "airpods", "bluez", "a2dp"]):
        return ("audio-headphones-symbolic", "Headphones")
    if "hdmi" in combined or "displayport" in combined:
        return ("video-display-symbolic", "HDMI Audio")
    return ("audio-volume-high-symbolic", "Speaker")


class calendarpopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(
            name="calendar-popup",
            halign=Gtk.Align.END,
            top_margin=48,
            side_margin=12,
            **kwargs,
        )
        self.calendar = Gtk.Calendar()
        self.card.add(self.calendar)


class ShellSettingsPopup(DismissiblePopup):
    def __init__(self, app_ref=None, control_center=None, **kwargs):
        super().__init__(name="shell-settings-popup", halign=Gtk.Align.CENTER, top_margin=52, **kwargs)
        self.app_ref = app_ref
        self.control_center = control_center

        header = CenterBox(
            start_children=Label(label="UT Shell Settings", style_classes=["popup-title"]),
            end_children=Button(
                child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU),
                on_clicked=lambda *_: self.set_visible(False),
            ),
        )

        power_row = Box(
            orientation="h",
            spacing=6,
            children=[
                Button(label="Saver", on_clicked=lambda *_: subprocess.Popen(["powerprofilesctl", "set", "power-saver"])),
                Button(label="Balanced", on_clicked=lambda *_: subprocess.Popen(["powerprofilesctl", "set", "balanced"])),
                Button(label="Perf", on_clicked=lambda *_: subprocess.Popen(["powerprofilesctl", "set", "performance"])),
            ],
        )

        night_row = Box(
            orientation="h",
            spacing=6,
            children=[
                Button(label="Off", on_clicked=lambda *_: os.system("pkill -x wlsunset")),
                Button(label="Warm (4500K)", on_clicked=lambda *_: os.system("pkill -x wlsunset; wlsunset -T 4500 &")),
                Button(label="Deep (3500K)", on_clicked=lambda *_: os.system("pkill -x wlsunset; wlsunset -T 3500 &")),
            ],
        )

        self.city_entry = Gtk.Entry()
        self.city_entry.set_text("Bengaluru")
        city_row = Box(
            orientation="h",
            spacing=6,
            children=[
                self.city_entry,
                Button(label="Apply", on_clicked=self.apply_weather_city),
            ],
        )

        tools_row = Box(
            orientation="v",
            spacing=6,
            children=[
                Button(
                    style_classes=["app-popup-item"],
                    label="Reload Shell CSS (styles/style.css)",
                    on_clicked=self.reload_css,
                ),
                Button(
                    style_classes=["app-popup-item"],
                    label="Display Layout (wdisplays)",
                    on_clicked=lambda *_: (os.system("wdisplays &"), self.set_visible(False)),
                ),
                Button(
                    style_classes=["app-popup-item"],
                    label="Open Full System Settings (Fallback)",
                    on_clicked=lambda *_: (
                        os.system("env XDG_CURRENT_DESKTOP=GNOME gnome-control-center &"),
                        self.set_visible(False),
                    ),
                ),
            ],
        )

        self.card.set_size_request(330, -1)
        self.card.add(header)
        self.card.add(Label(label="Power Profile", style_classes=["muted-text"]))
        self.card.add(power_row)
        self.card.add(Label(label="Night Light", style_classes=["muted-text"]))
        self.card.add(night_row)
        self.card.add(Label(label="Weather Location", style_classes=["muted-text"]))
        self.card.add(city_row)
        self.card.add(Label(label="Shell Utilities", style_classes=["muted-text"]))
        self.card.add(tools_row)

    def apply_weather_city(self, *_):
        city = self.city_entry.get_text().strip()
        if city and self.control_center:
            self.control_center.weather_city = city
            self.control_center.weather_label.set_label(f"Updating ({city})...")
            self.control_center.trigger_weather_refresh()

    def reload_css(self, *_):
        if self.app_ref:
            css_path = os.path.join(os.path.dirname(__file__), "styles/style.css")
            self.app_ref.set_stylesheet_from_file(css_path)


class WifiPopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(name="wifi-popup", halign=Gtk.Align.CENTER, top_margin=52, **kwargs)
        self.pending_ssid = None

        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.set_valign(Gtk.Align.CENTER)
        self.wifi_switch_handler = self.wifi_switch.connect("state-set", self.on_toggle_wifi)

        refresh_btn = Button(
            child=Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU),
            tooltip_text="Scan Networks",
            on_clicked=lambda *_: self.refresh_networks(rescan=True),
        )

        header = CenterBox(
            start_children=Label(label="Wi-Fi Networks", style_classes=["popup-title"]),
            end_children=Box(orientation="h", spacing=8, children=[refresh_btn, self.wifi_switch]),
        )

        self.status_label = Label(label="", style_classes=["muted-text"])

        self.pw_entry = Gtk.Entry()
        self.pw_entry.set_visibility(False)
        self.pw_entry.set_placeholder_text("Enter Wi-Fi password...")
        self.pw_entry.connect("activate", self.submit_password)

        self.pw_box = Box(
            orientation="h",
            spacing=6,
            children=[
                self.pw_entry,
                Button(label="Connect", on_clicked=self.submit_password),
            ],
        )
        self.pw_box.set_no_show_all(True)
        self.pw_box.set_visible(False)

        self.list_box = Box(orientation="v", spacing=6)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(260)
        scrolled.set_min_content_width(300)
        scrolled.add(self.list_box)

        self.card.add(header)
        self.card.add(self.status_label)
        self.card.add(self.pw_box)
        self.card.add(scrolled)

    def toggle(self):
        super().toggle()
        if self.get_visible():
            self.pw_box.set_visible(False)
            self.refresh_networks(rescan=False)

    def on_toggle_wifi(self, _switch, state):
        mode = "on" if state else "off"
        threading.Thread(
            target=lambda: (
                subprocess.run(["nmcli", "radio", "wifi", mode]),
                GLib.idle_add(self.refresh_networks, False),
            ),
            daemon=True,
        ).start()
        return False

    def refresh_networks(self, rescan=False):
        self.status_label.set_label("Scanning..." if rescan else "Loading...")

        def worker():
            radio = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True).stdout.strip()
            enabled = radio == "enabled"
            networks = []
            if enabled:
                cmd = ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"]
                if rescan:
                    cmd += ["--rescan", "yes"]
                out = subprocess.run(cmd, capture_output=True, text=True).stdout
                seen = set()
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        in_use, ssid, signal, sec = parts[0], parts[1], parts[2], parts[3]
                        if ssid and ssid not in seen:
                            seen.add(ssid)
                            networks.append((in_use == "*", ssid, int(signal or 0), bool(sec and sec != "--")))
            GLib.idle_add(self._render_networks, enabled, networks)

        threading.Thread(target=worker, daemon=True).start()

    def _render_networks(self, enabled, networks):
        self.wifi_switch.handler_block(self.wifi_switch_handler)
        self.wifi_switch.set_active(enabled)
        self.wifi_switch.handler_unblock(self.wifi_switch_handler)

        for child in list(self.list_box.get_children()):
            self.list_box.remove(child)
            child.destroy()

        if not enabled:
            self.status_label.set_label("Wi-Fi is turned off")
            return

        self.status_label.set_label(f"{len(networks)} networks found")
        for active, ssid, sig, locked in networks:
            icon = (
                "network-wireless-signal-excellent-symbolic"
                if sig >= 70
                else ("network-wireless-signal-good-symbolic" if sig >= 45 else "network-wireless-signal-weak-symbolic")
            )
            tag = "Connected" if active else f"{sig}%"
            btn = Button(
                style_classes=["app-popup-item", "active-row"] if active else ["app-popup-item"],
                child=CenterBox(
                    start_children=Box(
                        orientation="h",
                        spacing=8,
                        children=[
                            Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU),
                            Label(label=ssid),
                        ],
                    ),
                    end_children=Label(label=tag, style_classes=["muted-text"]),
                ),
                on_clicked=lambda *_, s=ssid, l=locked: self.connect_network(s, l),
            )
            self.list_box.add(btn)
        self.list_box.show_all()

    def connect_network(self, ssid, locked):
        self.status_label.set_label(f"Connecting to {ssid}...")

        def worker():
            res = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid], capture_output=True, text=True)
            if res.returncode == 0:
                GLib.idle_add(self.refresh_networks, False)
            elif locked:
                GLib.idle_add(self._prompt_password, ssid)
            else:
                GLib.idle_add(self.status_label.set_label, "Connection failed")

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_password(self, ssid):
        self.pending_ssid = ssid
        self.status_label.set_label(f"Password required for {ssid}")
        self.pw_entry.set_text("")
        self.pw_box.set_visible(True)
        self.pw_box.show_all()
        self.pw_entry.grab_focus()

    def submit_password(self, *_):
        password = self.pw_entry.get_text()
        ssid = self.pending_ssid
        if not ssid or not password:
            return
        self.pw_box.set_visible(False)
        self.status_label.set_label(f"Authenticating {ssid}...")

        def worker():
            res = subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                GLib.idle_add(self.refresh_networks, False)
            else:
                GLib.idle_add(self.status_label.set_label, "Wrong password or failed")

        threading.Thread(target=worker, daemon=True).start()


class BluetoothPopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(name="bluetooth-popup", halign=Gtk.Align.CENTER, top_margin=52, **kwargs)

        self.bt_switch = Gtk.Switch()
        self.bt_switch.set_valign(Gtk.Align.CENTER)
        self.bt_switch_handler = self.bt_switch.connect("state-set", self.on_toggle_bt)

        scan_btn = Button(
            child=Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU),
            tooltip_text="Scan for Bluetooth devices (5s)",
            on_clicked=lambda *_: self.refresh_devices(scan=True),
        )

        header = CenterBox(
            start_children=Label(label="Bluetooth", style_classes=["popup-title"]),
            end_children=Box(orientation="h", spacing=8, children=[scan_btn, self.bt_switch]),
        )

        self.status_label = Label(label="", style_classes=["muted-text"])
        self.list_box = Box(orientation="v", spacing=6)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(240)
        scrolled.set_min_content_width(300)
        scrolled.add(self.list_box)

        self.card.add(header)
        self.card.add(self.status_label)
        self.card.add(scrolled)

    def toggle(self):
        super().toggle()
        if self.get_visible():
            self.refresh_devices(scan=False)

    def on_toggle_bt(self, _switch, state):
        mode = "on" if state else "off"
        threading.Thread(
            target=lambda: (
                subprocess.run(["rfkill", "unblock", "bluetooth"]) if state else None,
                subprocess.run(["bluetoothctl", "power", mode]),
                GLib.idle_add(self.refresh_devices, False),
            ),
            daemon=True,
        ).start()
        return False

    def refresh_devices(self, scan=False):
        self.status_label.set_label("Scanning (5s)..." if scan else "Loading devices...")

        def worker():
            show_out = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True).stdout
            powered = "Powered: yes" in show_out
            devices = []
            if powered:
                if scan:
                    subprocess.run(["bluetoothctl", "--timeout", "5", "scan", "on"], capture_output=True)
                all_out = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
                conn_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
                for line in all_out.splitlines():
                    parts = line.split(" ", 2)
                    if len(parts) == 3 and parts[0] == "Device":
                        mac, name = parts[1], parts[2]
                        devices.append((mac, name, mac in conn_out))
            GLib.idle_add(self._render_devices, powered, devices)

        threading.Thread(target=worker, daemon=True).start()

    def _render_devices(self, powered, devices):
        self.bt_switch.handler_block(self.bt_switch_handler)
        self.bt_switch.set_active(powered)
        self.bt_switch.handler_unblock(self.bt_switch_handler)

        for child in list(self.list_box.get_children()):
            self.list_box.remove(child)
            child.destroy()

        if not powered:
            self.status_label.set_label("Bluetooth is off")
            return

        self.status_label.set_label(f"{len(devices)} devices")
        for mac, name, connected in devices:
            action = "Disconnect" if connected else "Connect"
            btn = Button(
                style_classes=["app-popup-item", "active-row"] if connected else ["app-popup-item"],
                child=CenterBox(
                    start_children=Box(
                        orientation="h",
                        spacing=8,
                        children=[
                            Gtk.Image.new_from_icon_name(
                                "audio-headphones-symbolic" if connected else "bluetooth-active-symbolic",
                                Gtk.IconSize.MENU,
                            ),
                            Label(label=name[:24]),
                        ],
                    ),
                    end_children=Label(label=action, style_classes=["muted-text"]),
                ),
                on_clicked=lambda *_, m=mac, c=connected: self.toggle_device(m, c),
            )
            self.list_box.add(btn)
        self.list_box.show_all()

    def toggle_device(self, mac, currently_connected):
        cmd = "disconnect" if currently_connected else "connect"
        self.status_label.set_label(f"{cmd.capitalize()}ing...")

        def worker():
            subprocess.run(["bluetoothctl", cmd, mac], capture_output=True)
            GLib.idle_add(self.refresh_devices, False)

        threading.Thread(target=worker, daemon=True).start()


class ControlCenterPopup(DismissiblePopup):
    def __init__(self, wifi_window=None, bt_window=None, shell_settings_window=None, **kwargs):
        super().__init__(
            name="control-center-popup",
            halign=Gtk.Align.CENTER,
            top_margin=48,
            side_margin=16,
            **kwargs,
        )
        self.wifi_window = wifi_window
        self.bt_window = bt_window
        self.shell_settings_window = shell_settings_window
        self.weather_city = "Bengaluru"
        self.current_weather_cond = "Overcast"

        # --- ROW 1: HEADER ---
        profile_img = Gtk.Image()
        try:
            profile_img.set_from_file("/home/utkarsh/.face")
        except Exception:
            profile_img.set_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DND)
        profile_img.set_pixel_size(40)

        username = os.getenv("USER", "Utkarsh").capitalize()
        self.profile_uptime_label = Label(label="Uptime: --")
        profile_info = Box(orientation="v", children=[Label(label=username), self.profile_uptime_label])

        self.uptime_fabricator = (
            Fabricator(poll_from=lambda *_: os.popen("uptime -p").read().strip(), interval=60000)
            .build()
            .connect("changed", lambda _, val: self.profile_uptime_label.set_label(f"Uptime: {val}"))
            .unwrap()
        )

        header_left = Box(orientation="h", spacing=10, children=[profile_img, profile_info])

        def run_and_close(cmd):
            os.system(cmd)
            self.set_visible(False)

        def open_subpopup(win):
            self.set_visible(False)
            if win:
                win.toggle()

        header_right = Box(
            orientation="h",
            spacing=5,
            children=[
                Button(
                    child=Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="UT Shell Settings",
                    on_clicked=lambda *_: open_subpopup(self.shell_settings_window),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("system-shutdown-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Power Menu",
                    on_clicked=lambda *_: run_and_close("(wlogout || env XDG_CURRENT_DESKTOP=GNOME gnome-control-center power) &"),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Close Control Center",
                    on_clicked=lambda *_: self.set_visible(False),
                ),
            ],
        )
        row1_header = CenterBox(start_children=header_left, end_children=header_right)

        self.bt_icon = Gtk.Image.new_from_icon_name("bluetooth-active-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        self.bt_button = Button(
            child=self.bt_icon,
            tooltip_text="Bluetooth",
            on_clicked=lambda *_: open_subpopup(self.bt_window),
        )

        toggles_left = Box(
            orientation="h",
            spacing=5,
            children=[
                Button(
                    child=Gtk.Image.new_from_icon_name("network-wireless-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Wi-Fi Networks",
                    on_clicked=lambda *_: open_subpopup(self.wifi_window),
                ),
                self.bt_button,
                Button(
                    child=Gtk.Image.new_from_icon_name("computer-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Display Settings",
                    on_clicked=lambda *_: run_and_close("(wdisplays || env XDG_CURRENT_DESKTOP=GNOME gnome-control-center display) &"),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("airplane-mode-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Toggle Airplane Mode",
                    on_clicked=lambda *_: os.system("rfkill toggle wifi; rfkill toggle bluetooth"),
                ),
            ],
        )

        toggles_right = Box(
            orientation="h",
            spacing=5,
            children=[
                Button(
                    child=Gtk.Image.new_from_icon_name("preferences-system-notifications-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Notification Settings",
                    on_clicked=lambda *_: run_and_close("env XDG_CURRENT_DESKTOP=GNOME gnome-control-center notifications &"),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("night-light-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Night Light",
                    on_clicked=lambda *_: os.system("pkill -x wlsunset || wlsunset -T 4500 &"),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("microphone-sensitivity-muted-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="Mute / Unmute Microphone",
                    on_clicked=lambda *_: os.system("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),
                ),
                Button(
                    child=Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                    tooltip_text="🗑️ Do you mean windows?",
                    on_clicked=lambda *_: run_and_close(
                        "(nautilus trash:/// || thunar trash:/// || dolphin trash:/ || xdg-open ~/.local/share/Trash/files) &"
                    ),
                ),
            ],
        )
        row2_toggles = Box(orientation="h", spacing=20, children=[toggles_left, toggles_right])

        def get_current_volume(target):
            try:
                raw = os.popen(f"wpctl get-volume {target}").read().strip()
                if "Volume:" in raw:
                    return int(float(raw.split()[1]) * 100)
            except Exception:
                pass
            return 50

        self.speaker_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.speaker_slider.set_value(get_current_volume("@DEFAULT_AUDIO_SINK@"))
        self.speaker_slider.connect(
            "value-changed",
            lambda slider: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {int(slider.get_value())}%"),
        )

        self.audio_in_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.audio_in_slider.set_value(get_current_volume("@DEFAULT_AUDIO_SOURCE@"))
        self.audio_in_slider.connect(
            "value-changed",
            lambda slider: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SOURCE@ {int(slider.get_value())}%"),
        )

        self.audio_out_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        self.audio_out_label = Label(label="Speaker")

        audio_out_box = Box(
            orientation="v",
            spacing=5,
            children=[
                Box(orientation="h", spacing=6, children=[self.audio_out_icon, self.audio_out_label]),
                self.speaker_slider,
            ],
        )

        audio_in_box = Box(
            orientation="v",
            spacing=5,
            children=[
                Box(
                    orientation="h",
                    spacing=5,
                    children=[
                        Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", Gtk.IconSize.BUTTON),
                        Label(label="Microphone"),
                    ],
                ),
                self.audio_in_slider,
            ],
        )
        row3_sliders = Box(orientation="h", spacing=15, children=[audio_out_box, audio_in_box])

        def update_audio_output_ui(_, info):
            icon_name, label_text = info
            self.audio_out_icon.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            self.audio_out_label.set_label(label_text)

        self.audio_output_fabricator = (
            Fabricator(poll_from=lambda *_: get_audio_output_info(), interval=2000)
            .build()
            .connect("changed", update_audio_output_ui)
            .unwrap()
        )

        self.weather_drop_icon = Gtk.Image.new_from_icon_name("weather-overcast", Gtk.IconSize.DIALOG)
        self.weather_drop_icon.set_pixel_size(64)
        self.weather_drop_label = Label(label=f"{self.weather_city} • Live Weather")

        self.weather_revealer = Revealer(
            transition_type="slide-down",
            transition_duration=250,
            child_revealed=False,
            child=Box(
                orientation="v",
                spacing=6,
                style_classes=["card"],
                children=[self.weather_drop_icon, self.weather_drop_label],
            ),
        )

        self.weather_label = Label(label="Loading weather...")
        self.weather_btn = Button(
            style_classes=["weather-banner"],
            child=Box(
                orientation="h",
                spacing=8,
                children=[
                    Gtk.Image.new_from_icon_name("weather-overcast-symbolic", Gtk.IconSize.MENU),
                    self.weather_label,
                ],
            ),
            on_clicked=lambda *_: self.weather_revealer.set_reveal_child(
                not self.weather_revealer.get_reveal_child()
            ),
        )

        row4_weather = Box(orientation="v", spacing=6, children=[self.weather_btn, self.weather_revealer])

        self.weather_fabricator = (
            Fabricator(poll_from=self._fetch_weather_data, interval=600000)
            .build()
            .connect("changed", self._on_weather_updated)
            .unwrap()
        )

        self.cpu_label = Label(label="0%")
        self.temp_label = Label(label="0°C")
        self.ram_label = Label(label="0%")
        self.disk_label = Label(label="0%")

        def make_stat_pill(icon_name, value_label):
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            icon.set_pixel_size(16)
            return Box(orientation="h", spacing=6, style_classes=["stat-card"], children=[icon, value_label])

        row5_stats = Box(
            orientation="h",
            spacing=8,
            children=[
                make_stat_pill("processor-symbolic", self.cpu_label),
                make_stat_pill("sensors-temperature-symbolic", self.temp_label),
                make_stat_pill("drive-multidisk-symbolic", self.ram_label),
                make_stat_pill("drive-harddisk-symbolic", self.disk_label),
            ],
        )

        def poll_system_stats(*_):
            cpu = os.popen("top -bn1 | awk '/Cpu\\(s\\)/ {print int($2 + $4)}' 2>/dev/null || echo 0").read().strip()
            temp = os.popen("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -n1 | awk '{print int($1/1000)}' || echo 0").read().strip()
            ram = os.popen("free | awk '/Mem:/ {print int($3/$2 * 100)}' 2>/dev/null || echo 0").read().strip()
            disk = os.popen("df -h / | awk 'NR==2 {print $5}' 2>/dev/null || echo 0%").read().strip()
            return (cpu or "0", temp or "0", ram or "0", disk or "0%")

        def update_system_stats(_, stats):
            cpu, temp, ram, disk = stats
            self.cpu_label.set_label(f"{cpu}%")
            self.temp_label.set_label(f"{temp}°C")
            self.ram_label.set_label(f"{ram}%")
            self.disk_label.set_label(f"{disk}")

        self.stats_fabricator = (
            Fabricator(poll_from=poll_system_stats, interval=2000)
            .build()
            .connect("changed", update_system_stats)
            .unwrap()
        )

        self.main_box = Box(
            orientation="v",
            spacing=12,
            children=[row1_header, row2_toggles, row3_sliders, row4_weather, row5_stats],
        )
        self.card.add(self.main_box)

    def _get_smart_icon(self, condition, hour_string):
        hour = int(hour_string)
        is_day = 6 <= hour < 18
        cond = condition.lower()

        if "rain" in cond or "drizzle" in cond or "shower" in cond:
            return "weather-showers"
        elif "storm" in cond or "thunder" in cond:
            return "weather-storm"
        elif "snow" in cond:
            return "weather-snow"
        elif "fog" in cond or "mist" in cond or "haze" in cond:
            return "weather-fog"
        elif "cloud" in cond or "overcast" in cond:
            if "partly" in cond or "few" in cond:
                return "weather-few-clouds" if is_day else "weather-few-clouds-night"
            return "weather-overcast"
        else:
            return "weather-clear" if is_day else "weather-clear-night"

    def _fetch_weather_data(self, *_):
        try:
            city = self.weather_city.replace(" ", "+")
            raw_data = os.popen(f"curl -sL --max-time 5 'https://wttr.in/{city}?format=%C|%t'").read().strip()
            if "|" in raw_data:
                cond, temp = raw_data.split("|")
                self.current_weather_cond = cond.strip()
                clean_temp = temp.replace("+", "").strip()
                return f"{self.current_weather_cond}, {clean_temp}"
        except Exception:
            pass
        return "Weather Unavailable"

    def _on_weather_updated(self, _, weather_str):
        self.weather_label.set_label(weather_str)
        smart_icon = self._get_smart_icon(self.current_weather_cond, time.strftime("%H"))
        self.weather_drop_icon.set_from_icon_name(smart_icon, Gtk.IconSize.DIALOG)
        self.weather_drop_icon.set_pixel_size(64)
        self.weather_drop_label.set_label(f"{self.weather_city} • {self.current_weather_cond}")

    def trigger_weather_refresh(self):
        threading.Thread(
            target=lambda: GLib.idle_add(self._on_weather_updated, None, self._fetch_weather_data()),
            daemon=True,
        ).start()


class AppLauncherPopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(
            name="launcher-popup-window",
            halign=Gtk.Align.START,
            top_margin=48,
            side_margin=12,
            **kwargs,
        )
        self.all_apps = []
        for app in Gio.AppInfo.get_all():
            if app.should_show():
                icon = app.get_icon()
                icon_name = icon.to_string() if icon else "application-x-executable"
                self.all_apps.append(
                    {
                        "name": app.get_display_name() or app.get_name(),
                        "icon": icon_name,
                        "app_info": app,
                    }
                )
        self.all_apps.sort(key=lambda x: x["name"].lower())

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search applications...")
        self.search_entry.connect("search-changed", self.on_search_changed)

        header_box = CenterBox(
            start_children=Label(label="Applications", style_classes=["popup-title"]),
            end_children=Button(
                child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU),
                style_classes=["close-btn"],
                on_clicked=lambda *_: self.set_visible(False),
            ),
        )
        self.apps_list_box = Box(orientation="v", spacing=6)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_min_content_height(360)
        self.scrolled.set_min_content_width(290)
        self.scrolled.add(self.apps_list_box)

        self.main_card = Box(
            orientation="v",
            spacing=10,
            style_classes=["apps-popup-card"],
            children=[header_box, self.search_entry, self.scrolled],
        )
        self.card.add(self.main_card)
        self.populate_apps("")

    def toggle(self):
        super().toggle()
        if self.get_visible():
            self.search_entry.set_text("")
            self.search_entry.grab_focus()

    def on_search_changed(self, entry):
        self.populate_apps(entry.get_text().strip().lower())

    def populate_apps(self, query=""):
        for child in list(self.apps_list_box.get_children()):
            self.apps_list_box.remove(child)
            child.destroy()

        matches = [a for a in self.all_apps if query in a["name"].lower()][:40]

        for app in matches:
            img = Gtk.Image.new_from_icon_name(app["icon"], Gtk.IconSize.LARGE_TOOLBAR)
            img.set_pixel_size(24)

            row_btn = Button(
                style_classes=["app-popup-item"],
                child=Box(orientation="h", spacing=10, children=[img, Label(label=app["name"])]),
                on_clicked=lambda *_, a_info=app["app_info"]: self.launch_app(a_info),
            )
            self.apps_list_box.add(row_btn)

        self.apps_list_box.show_all()

    def launch_app(self, app_info):
        try:
            app_info.launch([], None)
        except Exception:
            pass
        self.set_visible(False)


class AppsPopup(DismissiblePopup):
    def __init__(self, **kwargs):
        super().__init__(
            name="apps-popup-window",
            halign=Gtk.Align.START,
            top_margin=48,
            side_margin=56,
            **kwargs,
        )
        self.apps_list_box = Box(orientation="v", spacing=6)

        header_box = CenterBox(
            start_children=Label(label="Open Windows", style_classes=["popup-title"]),
            end_children=Button(
                child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU),
                style_classes=["close-btn"],
                on_clicked=lambda *_: self.set_visible(False),
            ),
        )

        self.main_card = Box(
            orientation="v",
            spacing=10,
            style_classes=["apps-popup-card"],
            children=[header_box, self.apps_list_box],
        )
        self.card.add(self.main_card)

    def update_apps(self, apps):
        for child in list(self.apps_list_box.get_children()):
            self.apps_list_box.remove(child)
            child.destroy()

        if not apps:
            self.apps_list_box.add(Label(label="No open windows"))
            self.apps_list_box.show_all()
            return

        for app in apps:
            full_title = app.get("title") or app.get("app_id", "App")
            if len(full_title) > 42:
                full_title = full_title[:40] + ".."

            img = Gtk.Image.new_from_icon_name(app["app_id"], Gtk.IconSize.LARGE_TOOLBAR)
            img.set_pixel_size(22)

            row_btn = Button(
                style_classes=["app-popup-item"],
                child=Box(orientation="h", spacing=10, children=[img, Label(label=full_title)]),
                on_clicked=lambda _, vid=app["id"]: (focus_window(vid), self.set_visible(False)),
            )
            self.apps_list_box.add(row_btn)

        self.apps_list_box.show_all()


class StatusBar(Window):
    def __init__(
        self,
        calendar_window=None,
        center_window=None,
        apps_window=None,
        launcher_window=None,
        **kwargs,
    ):
        super().__init__(
            name="top-bar-window",
            layer="top",
            anchor="top left right",
            exclusivity="auto",
            **kwargs,
        )
        self.calendar_window = calendar_window
        self.center_window = center_window
        self.apps_window = apps_window
        self.launcher_window = launcher_window

        # Left Island
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        launcher_icon.set_pixel_size(20)

        self.launcher_btn = Button(
            style_classes=["launcher-btn"],
            tooltip_text="Applications Menu",
            child=launcher_icon,
            on_clicked=lambda *_: self.launcher_window.toggle() if self.launcher_window else None,
        )

        self.app_container = Box(orientation="h", spacing=6)

        self.more_apps_label = Label(label="+0")
        self.more_apps_btn = Button(
            style_classes=["more-apps-btn"],
            tooltip_text="Show all open windows",
            child=Box(orientation="h", spacing=4, children=[self.more_apps_label]),
            on_clicked=lambda *_: self.apps_window.toggle() if self.apps_window else None,
        )

        self.left_island = Box(
            orientation="h",
            spacing=8,
            style_classes=["bar-island", "island-left"],
            children=[self.launcher_btn, self.app_container, self.more_apps_btn],
        )

        # Middle Island
        username = os.getenv("USER", "Utkarsh").capitalize()
        self.user_label = Label(label=username, style_classes=["username-cursive"])

        self.middle_user_btn = Button(
            style_classes=["middle-user-btn"],
            tooltip_text="Open Control Center",
            child=self.user_label,
            on_clicked=lambda *_: self.center_window.toggle() if self.center_window else None,
        )

        self.middle_island = Box(
            orientation="h",
            spacing=0,
            style_classes=["bar-island", "island-center"],
            children=[self.middle_user_btn],
        )

        # Right Island
        self.bat_icon = Gtk.Image.new_from_icon_name("battery-good-symbolic", Gtk.IconSize.MENU)
        self.bat_label = Label(label="80%", style_classes=["status-text"])

        self.right_status_btn = Button(
            style_classes=["right-status-pill"],
            child=Box(orientation="h", spacing=6, children=[self.bat_icon, self.bat_label]),
            on_clicked=lambda *_: self.center_window.toggle() if self.center_window else None,
        )

        self.date_label = Label(label=time.strftime("%a, %b %d"), style_classes=["date-pill"])
        self.time_label = Label(label=time.strftime("%I:%M:%S %p"), style_classes=["clock-text"])

        self.clock_btn = Button(
            style_classes=["clock-island-btn"],
            child=Box(orientation="h", spacing=10, children=[self.date_label, self.time_label]),
            on_clicked=lambda *_: self.calendar_window.toggle() if self.calendar_window else None,
        )

        self.right_island = Box(
            orientation="h",
            spacing=10,
            style_classes=["bar-island", "island-right"],
            children=[self.right_status_btn, self.clock_btn],
        )

        self.bar_layout = CenterBox(
            name="bar-transparent-root",
            style_classes=["bar-transparent-root"],
            start_children=self.left_island,
            center_children=self.right_island,  
            end_children=self.middle_island,    
)
        self.add(self.bar_layout)
        self.bar_layout.show_all()

        self.apps_fabricator = (
            Fabricator(poll_from=lambda *_: get_wayfire(), interval=1000)
            .build()
            .connect("changed", lambda _, apps: self.update_taskbar(apps))
            .unwrap()
        )

        self.clock_fabricator = (
            Fabricator(
                poll_from=lambda *_: (
                    time.strftime("%a, %b %d"),
                    time.strftime("%I:%M:%S %p"),
                    os.popen("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || echo 100").read().strip(),
                ),
                interval=1000,
            )
            .build()
            .connect("changed", self.refresh_status)
            .unwrap()
        )

    def refresh_status(self, _, data):
        date_str, time_str, bat_cap = data
        self.date_label.set_label(date_str)
        self.time_label.set_label(time_str)
        if bat_cap:
            self.bat_label.set_label(f"{bat_cap.splitlines()[0]}%")

    def update_taskbar(self, window_list):
        if self.apps_window:
            self.apps_window.update_apps(window_list)

        for child in list(self.app_container.get_children()):
            self.app_container.remove(child)
            child.destroy()

        for app in window_list[:3]:
            short_title = app.get("title") or app.get("app_id", "App")
            if len(short_title) > 15:
                short_title = short_title[:13] + ".."

            icon = Gtk.Image.new_from_icon_name(app["app_id"], Gtk.IconSize.MENU)
            icon.set_pixel_size(18)

            btn = Button(
                style_classes=["taskbar-app-btn"],
                tooltip_text=app.get("title", ""),
                child=Box(orientation="h", spacing=6, children=[icon, Label(label=short_title)]),
                on_clicked=lambda *_, vid=app["id"]: focus_window(vid),
            )
            self.app_container.add(btn)

        self.app_container.show_all()

        extra_count = max(0, len(window_list) - 3)
        if extra_count > 0:
            self.more_apps_label.set_label(f"+{extra_count}")
            self.more_apps_btn.set_visible(True)
        else:
            self.more_apps_label.set_label("All")
            self.more_apps_btn.set_visible(len(window_list) > 0)


if __name__ == "__main__":
    wifi_pop = WifiPopup()
    bt_pop = BluetoothPopup()
    shell_settings_pop = ShellSettingsPopup()
    my_popup = AnimatedClockPopup()
    center_pop = ControlCenterPopup(
        wifi_window=wifi_pop,
        bt_window=bt_pop,
        shell_settings_window=shell_settings_pop,
    )
    apps_pop = AppsPopup()
    launcher_pop = AppLauncherPopup()

    bar = StatusBar(
        calendar_window=my_popup,
        center_window=center_pop,
        apps_window=apps_pop,
        launcher_window=launcher_pop,
    )

    app = Application(
        "ut-shell",
        bar,
        my_popup,
        center_pop,
        apps_pop,
        launcher_pop,
        wifi_pop,
        bt_pop,
        shell_settings_pop,
    )
    shell_settings_pop.app_ref = app
    shell_settings_pop.control_center = center_pop

    app.set_stylesheet_from_file(os.path.join(os.path.dirname(__file__), "styles/style.css"))
    app.run()