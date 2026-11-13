import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
import time
import os
import fabric
from fabric import Application, Fabricator
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.eventbox import EventBox
from fabric.widgets.revealer import Revealer
from gi.repository import Gtk
import socket,json
from wayfire import WayfireSocket
import subprocess

def get_wayfire():
    try:
        sock = WayfireSocket(allow_manual_search=True)
        views = sock.list_views()     
        theme = Gtk.IconTheme.get_default()
        
        app_list = []
        for view in views:
            if view.get('role') == 'toplevel' and view.get('mapped') is True:
                app_name = view.get('app-id')
                view_id = view.get('id')
                title = view.get('title', app_name)
                
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
                            app_name = "com.visualstudio.code" if theme.has_icon("com.visualstudio.code") else "text-editor"
                        else:
                            app_name = "application-x-executable"

                    app_list.append({"id": view_id, "app_id": app_name, "title": title})
        return app_list
    except Exception as e:
        print(f"IPC Error: {e}")
        return []

def focus_window(view_id):
    print(f"Attempting to focus window ID: {view_id}")
    try:
        sock = WayfireSocket(allow_manual_search=True)
        # Attempt the standard focus method
        if hasattr(sock, 'set_focus'):
            sock.set_focus(view_id)
        else:
            print("Focus method missing. check your pywayfire library.")
    except Exception as e:
        print(f"Focus Error: {e}")


class calendarpopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            anchor="top right",
            margin=(50, 10, 10, 10),
            visible=False,
            **kwargs
        )
        self.children = Gtk.Calendar()
        self.dismiss_layer = DismissLayer(on_dismiss=self.hide)
        self.connect("show", lambda *_: self.dismiss_layer.show_all())
        self.connect("hide", lambda *_: self.dismiss_layer.hide())

class DismissLayer(Window):
    def __init__(self, on_dismiss, **kwargs):
        self.event_box = EventBox()
        super().__init__(
            layer="top",
            anchor="top left right bottom",
            keyboard_mode="none",
            child=self.event_box,
            visible=False,
            style="background-color: transparent;",
            **kwargs
        )
        self.event_box.connect("button-release-event", lambda *_: on_dismiss())

class settingspopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            anchor="top left",
            margin=(45, 0, 0, 10), 
            visible=False,
            keyboard_mode="on-demand",
            **kwargs
        )
        # sound slider
        self.dismiss_layer = DismissLayer(on_dismiss=self.hide)
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.slider.set_size_request(180, -1)
        self.slider.set_draw_value(True)
        self.slider.set_range(0, 100)
        self.slider_handler = self.slider.connect(
            "value-changed",
            lambda scale: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {scale.get_value() / 100}")
        )
        self.connect("show", self.sync_state)
        self.connect("hide", lambda *_: self.dismiss_layer.hide())
        
        # Wi-Fi toggle
        self.wifi_label = Label(label="Wi-Fi: --")
        
        self.wifi_switch = Gtk.Switch()
        self.wifi_revealer = Gtk.Revealer()
        self.password_entry = Gtk.Entry()
        self.wifi_expand_button = Button(label = "⌄")
        self.wifi_expand_button.connect("clicked", lambda *_: [self.scan_networks(), self.wifi_revealer.set_reveal_child(not self.wifi_revealer.get_reveal_child())])
        self.wifi_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.handler_box = Box(orientation="v",  spacing=5,)
        self.password_entry.set_placeholder_text("Password")
        self.password_entry.set_visibility(False)
        self.password_entry.connect("activate", self.connect_with_password)
        self.password_entry.hide()
        self.handler_box.add(self.password_entry)
        self.wifi_revealer.add(self.handler_box)
        self.wifi_switch.set_valign(Gtk.Align.CENTER)
        self.wifi_handler = self.wifi_switch.connect(
            "state-set",
            lambda switch, state: os.system("nmcli radio wifi on" if state else "nmcli radio wifi off")
        )
        
        wifi_box = Box(orientation="h",
         spacing=10, children=[self.wifi_label,self.wifi_switch,self.wifi_expand_button])

        # adding both into a main box
        self.main_box = Box(orientation="v", spacing=10,
            children=[self.slider, wifi_box,self.wifi_revealer])

        self.children = self.main_box

    def scan_networks(self, *args):
        networks = os.popen("nmcli -t -f SSID dev wifi").read().strip().splitlines()
        saved_networks = os.popen("nmcli -t -f NAME connection show").read().strip().splitlines()
        for child in self.handler_box.get_children():
            if child != self.password_entry:
                self.handler_box.remove(child)
                child.destroy()

        for network in networks:
            if network in saved_networks:
               button = Button(
                    label=network,
                     on_clicked=lambda *_, target=network: [
                    self.password_entry.hide(),
                    os.system(f"nmcli dev wifi connect '{target}'")
                ]
            )
            else:
                button = Button(
                     label=network,
                        on_clicked=lambda *_, target=network: [
                        setattr(self, 'pending_ssid', target),
                        self.password_entry.set_placeholder_text(f"Password for {target}"),
                        self.password_entry.show(),
                        self.password_entry.grab_focus()    
                        ]               
                )
            self.handler_box.add(button)
        self.handler_box.show_all()
        self.password_entry.hide()



    def sync_state(self, *args):
        # volume
        self.dismiss_layer.show_all()
        volume = os.popen("wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print $2}'").read().strip()
        if volume:
            val = float(volume) * 100
            self.slider.handler_block(self.slider_handler)
            self.slider.set_value(val)
            self.slider.handler_unblock(self.slider_handler)
        # Wi-Fi
        wifi_state = os.popen("nmcli radio wifi").read().strip()
        if wifi_state:
            state = wifi_state.lower() == "enabled"
            self.wifi_switch.handler_block(self.wifi_handler)
            self.wifi_switch.set_active(state)
            self.wifi_switch.handler_unblock(self.wifi_handler)
            ssid = os.popen("nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes' | cut -d: -f2").read().strip()
            self.wifi_label.set_label(f"Wi-Fi: {ssid}")
        self.connect_with_password = lambda entry: self._connect_with_password(entry)

    def  connect_with_password(self, entry):
            password = entry.get_text()
            os.system(f"nmcli dev wifi connect '{self.pending_ssid}' password '{password}'")
            entry.set_text("")
            entry.hide()

class ControlCenterPopup(Window):
    def __init__(self, **kwargs):
        
       
        profile_img = Gtk.Image()
        try:
            profile_img.set_from_file("/home/utkarsh/.face")
        except:
            profile_img.set_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DND)
        profile_img.set_pixel_size(40)

        username = os.getenv("USER").capitalize()
        self.profile_uptime_label = Label(label="Uptime: --")
        profile_info = Box(orientation="v", children=[
            Label(label=username),
            self.profile_uptime_label
        ])
        self.uptime_fabricator = Fabricator(
            poll_from=lambda *_: os.popen("uptime -p").read().strip(),
            interval=60000).build().connect("changed", lambda _, val: self.profile_uptime_label.set_label(f"Uptime: {val}")).unwrap()
        
        header_left = Box(orientation="h", spacing=10, children=[profile_img, profile_info])
        
        header_right = Box(orientation="h", spacing=5, children=[
            Button(child=Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("system-shutdown-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        ])
        row1_header = CenterBox(start_children=header_left, end_children=header_right)

        
        self.bt_icon = Gtk.Image.new_from_icon_name("bluetooth-active-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        
        self.bt_button = Button(
            child=self.bt_icon,
on_clicked=lambda *_: os.system("env XDG_CURRENT_DESKTOP=GNOME gnome-control-center bluetooth &")        )
        


        toggles_left = Box(orientation="h", spacing=5, children=[
            Button(
                child=Gtk.Image.new_from_icon_name("network-wireless-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                on_clicked=lambda *_: os.system("env XDG_CURRENT_DESKTOP=GNOME gnome-control-center wifi &")
            ),
            
            self.bt_button, 
            
            Button(child=Gtk.Image.new_from_icon_name("computer-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("airplane-mode-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        ])

       
        
        toggles_right = Box(orientation="h", spacing=5, children=[
            Button(child=Gtk.Image.new_from_icon_name("preferences-system-notifications-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("night-light-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("microphone-sensitivity-muted-symbolic", Gtk.IconSize.LARGE_TOOLBAR)),
            Button(child=Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        ])
        row2_toggles = Box(orientation="h", spacing=20, children=[toggles_left, toggles_right])

        def get_current_volume(target):
                    try:
                        raw = os.popen(f"wpctl get-volume {target}").read().strip()
                        if "Volume:" in raw:
                            vol_float = float(raw.split()[1])
                            return int(vol_float * 100)
                    except Exception:
                        pass
                    return 50 

        self.speaker_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        
        current_speaker_vol = get_current_volume("@DEFAULT_AUDIO_SINK@")
        self.speaker_slider.set_value(current_speaker_vol)
        
        self.speaker_slider.connect(
            "value-changed", 
            lambda slider: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {int(slider.get_value())}%")
        )


        self.audio_in_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        
        current_mic_vol = get_current_volume("@DEFAULT_AUDIO_SOURCE@")
        self.audio_in_slider.set_value(current_mic_vol)
        
        self.audio_in_slider.connect(
            "value-changed", 
            lambda slider: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SOURCE@ {int(slider.get_value())}%")
        )
        self.speaker_slider.connect(
            "value-changed", 
            lambda slider: os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {int(slider.get_value())}%")
        )

        audio_out_box = Box(orientation="v", spacing=5, children=[
            Box(orientation="h", spacing=5, children=[
                Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                Label(label="Speaker") 
            ]),
            self.speaker_slider 
        ])
        
        audio_in_box = Box(orientation="v", spacing=5, children=[
            Box(orientation="h", spacing=5, children=[
                Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", Gtk.IconSize.BUTTON),
                Label(label="Microphone")
            ]),
            self.audio_in_slider
        ])
        row3_sliders = Box(orientation="h", spacing=15, children=[audio_out_box, audio_in_box])

        def get_smart_icon(condition, hour_string):
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

        self.current_weather_cond = "Overcast"

        self.weather_drop_icon = Gtk.Image.new_from_icon_name("weather-overcast", Gtk.IconSize.DIALOG)
        self.weather_drop_icon.set_pixel_size(64)

        self.weather_drop_label = Label(label="Bengaluru • Live Weather")

        self.weather_revealer = Revealer(
            transition_type="slide-down",
            transition_duration=250,
            child_revealed=False,
            child=Box(
                orientation="v",
                spacing=6,
                style_classes=["card"],
                children=[
                    self.weather_drop_icon,
                    self.weather_drop_label
                ]
            )
        )

        self.weather_label = Label(label="Loading weather...")
        self.weather_btn = Button(
            style_classes=["weather-banner"],
            child=Box(
                orientation="h",
                spacing=8,
                children=[
                    Gtk.Image.new_from_icon_name("weather-overcast-symbolic", Gtk.IconSize.MENU),
                    self.weather_label
                ]
            ),
            on_clicked=lambda *_: self.weather_revealer.set_reveal_child(
                not self.weather_revealer.get_reveal_child()
            )
        )

        row4_weather = Box(
            orientation="v",
            spacing=6,
            children=[
                self.weather_btn,
                self.weather_revealer
            ]
        )

        def fetch_weather_data(*_):
            try:
                raw_data = os.popen("curl -s 'wttr.in/Bengaluru?format=%C|%t'").read().strip()
                if "|" in raw_data:
                    cond, temp = raw_data.split("|")
                    self.current_weather_cond = cond.strip()
                    clean_temp = temp.replace("+", "").strip()
                    return f"{self.current_weather_cond}, {clean_temp}"
            except Exception:
                pass
            return "Weather Unavailable"

        def on_weather_updated(_, weather_str):
            self.weather_label.set_label(weather_str)
            current_hour = time.strftime("%H")
            smart_icon = get_smart_icon(self.current_weather_cond, current_hour)
            # Updates the drop-down icon dynamically without re-adding widgets to a Box
            self.weather_drop_icon.set_from_icon_name(smart_icon, Gtk.IconSize.DIALOG)
            self.weather_drop_icon.set_pixel_size(64)
            self.weather_drop_label.set_label(f"Condition: {self.current_weather_cond}")

        self.weather_fabricator = Fabricator(
            poll_from=fetch_weather_data,
            interval=600000
        ).build().connect("changed", on_weather_updated).unwrap()

from gi.repository import Gio

class AppLauncherPopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            name="launcher-popup-window",
            layer="top",
            anchor="top left",
            margin="8px 0px 0px 12px",
            exclusivity="none",
            keyboard_mode="on-demand",
            visible=False,
            **kwargs
        )
        self.all_apps = []
        for app in Gio.AppInfo.get_all():
            if app.should_show():
                icon = app.get_icon()
                icon_name = icon.to_string() if icon else "application-x-executable"
                self.all_apps.append({
                    "name": app.get_display_name() or app.get_name(),
                    "icon": icon_name,
                    "app_info": app
                })
        self.all_apps.sort(key=lambda x: x["name"].lower())

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search applications...")
        self.search_entry.connect("search-changed", self.on_search_changed)

        header_box = CenterBox(
            start_children=Label(label="Applications", style_classes=["popup-title"]),
            end_children=Button(
                child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU),
                style_classes=["close-btn"],
                on_clicked=lambda *_: self.set_visible(False)
            )
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
            style_classes=["popup-card", "apps-popup-card"],
            children=[header_box, self.search_entry, self.scrolled]
        )
        self.add(self.main_card)
        self.populate_apps("")
        self.main_card.show_all()

    def on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        self.populate_apps(query)

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
                child=Box(
                    orientation="h",
                    spacing=10,
                    children=[img, Label(label=app["name"])]
                ),
                on_clicked=lambda *_, a_info=app["app_info"]: self.launch_app(a_info)
            )
            self.apps_list_box.add(row_btn)

        self.apps_list_box.show_all()

    def launch_app(self, app_info):
        try:
            app_info.launch([], None)
        except Exception:
            pass
        self.set_visible(False)


class AppsPopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            name="apps-popup-window",
            layer="top",
            anchor="top left",
            margin="8px 0px 0px 56px",
            exclusivity="none",
            visible=False,
            **kwargs
        )
        self.apps_list_box = Box(orientation="v", spacing=6)

        header_box = CenterBox(
            start_children=Label(label="Open Windows", style_classes=["popup-title"]),
            end_children=Button(
                child=Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU),
                style_classes=["close-btn"],
                on_clicked=lambda *_: self.set_visible(False)
            )
        )

        self.main_card = Box(
            orientation="v",
            spacing=10,
            style_classes=["popup-card", "apps-popup-card"],
            children=[header_box, self.apps_list_box]
        )
        self.add(self.main_card)
        self.main_card.show_all()

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
                child=Box(
                    orientation="h",
                    spacing=10,
                    children=[img, Label(label=full_title)]
                ),
                on_clicked=lambda _, vid=app["id"]: (
                    focus_window(vid),
                    self.set_visible(False)
                )
            )
            self.apps_list_box.add(row_btn)

        self.apps_list_box.show_all()


class StatusBar(Window):
    def __init__(self, calendar_window=None, settings_window=None, center_window=None, apps_window=None, launcher_window=None, **kwargs):
        super().__init__(
            name="top-bar-window",
            layer="top",
            anchor="top left right",
            exclusivity="auto",
            **kwargs
        )
        self.calendar_window = calendar_window
        self.settings_window = settings_window
        self.center_window = center_window
        self.apps_window = apps_window
        self.launcher_window = launcher_window

    
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        launcher_icon.set_pixel_size(20)

        self.launcher_btn = Button(
            style_classes=["launcher-btn"],
            tooltip_text="Applications Menu",
            child=launcher_icon,
            on_clicked=self.toggle_launcher_popup
        )

        self.app_container = Box(orientation="h", spacing=6)

        self.more_apps_label = Label(label="+0")
        self.more_apps_btn = Button(
            style_classes=["more-apps-btn"],
            tooltip_text="Show all open windows",
            child=Box(
                orientation="h",
                spacing=4,
                children=[self.more_apps_label]
            ),
            on_clicked=self.toggle_apps_popup
        )

        self.left_island = Box(
            orientation="h",
            spacing=8,
            style_classes=["bar-island", "island-left"],
            children=[
                self.launcher_btn,
                self.app_container,
                self.more_apps_btn
            ]
        )


        username = os.getenv("USER", "Utkarsh").capitalize()
        self.user_label = Label(
            label=username,
            style_classes=["username-cursive"]
        )

        self.middle_user_btn = Button(
            style_classes=["middle-user-btn"],
            tooltip_text="Open Control Center",
            child=self.user_label,
            on_clicked=self.toggle_control_center
        )

        self.middle_island = Box(
            orientation="h",
            spacing=0,
            style_classes=["bar-island", "island-center"],
            children=[self.middle_user_btn]
        )


        self.bat_icon = Gtk.Image.new_from_icon_name("battery-good-symbolic", Gtk.IconSize.MENU)
        self.bat_label = Label(label="80%", style_classes=["status-text"])

        self.right_status_btn = Button(
            style_classes=["right-status-pill"],
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    self.bat_icon,
                    self.bat_label
                ]
            ),
            on_clicked=self.toggle_control_center
        )

        self.date_label = Label(label=time.strftime("%a, %b %d"), style_classes=["date-pill"])
        self.time_label = Label(label=time.strftime("%I:%M:%S %p"), style_classes=["clock-text"])

        self.clock_btn = Button(
            style_classes=["clock-island-btn"],
            child=Box(
                orientation="h",
                spacing=10,
                children=[self.date_label, self.time_label]
            ),
            on_clicked=self.toggle_calendar
        )

        self.right_island = Box(
            orientation="h",
            spacing=10,
            style_classes=["bar-island", "island-right"],
            children=[
                self.right_status_btn,
                self.clock_btn
            ]
        )

        self.bar_layout = CenterBox(
            name="bar-transparent-root",
            style_classes=["bar-transparent-root"],
            start_children=self.left_island,
            center_children=self.middle_island,
            end_children=self.right_island
        )
        self.add(self.bar_layout)

        self.bar_layout.show_all()

        self.apps_fabricator = Fabricator(
            poll_from=lambda *_: get_wayfire(),
            interval=1000
        ).build().connect("changed", lambda _, apps: self.update_taskbar(apps)).unwrap()

        self.clock_fabricator = Fabricator(
            poll_from=lambda *_: (
                time.strftime("%a, %b %d"),
                time.strftime("%I:%M:%S %p"),
                os.popen("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || echo 100").read().strip(),
                os.popen("wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null").read().strip(),
                os.popen("bluetoothctl show 2>/dev/null").read().strip()
            ),
            interval=1000
        ).build().connect("changed", self.refresh_status).unwrap()

    def toggle_launcher_popup(self, *_):
        if self.launcher_window:
            if self.launcher_window.get_visible():
                self.launcher_window.set_visible(False)
            else:
                self.launcher_window.show_all()
                self.launcher_window.set_visible(True)
                self.launcher_window.search_entry.set_text("")
                self.launcher_window.search_entry.grab_focus()

    def toggle_apps_popup(self, *_):
        if self.apps_window:
            if self.apps_window.get_visible():
                self.apps_window.set_visible(False)
            else:
                self.apps_window.show_all()
                self.apps_window.set_visible(True)

    def toggle_control_center(self, *_):
        if self.center_window:
            if self.center_window.get_visible():
                self.center_window.set_visible(False)
            else:
                self.center_window.show_all()
                self.center_window.set_visible(True)

    def toggle_calendar(self, *_):
        if self.calendar_window:
            if self.calendar_window.get_visible():
                self.calendar_window.set_visible(False)
            else:
                self.calendar_window.show_all()
                self.calendar_window.set_visible(True)

    def refresh_status(self, _, data):
        date_str, time_str, bat_cap, vol_raw, bt_raw = data
        self.date_label.set_label(date_str)
        self.time_label.set_label(time_str)
        if bat_cap:
            self.bat_label.set_label(f"{bat_cap.splitlines()[0]}%")
        self.sound_icon_update(vol_raw)
        self.bluetooth_icon_update(bt_raw)

    def sound_icon_update(self, val):
        raw_string = str(val).strip()
        if "[MUTED]" in raw_string:
            icon = "audio-volume-muted-symbolic"
        else:
            try:
                clean_num = raw_string.replace("Volume:", "").strip()
                volume = int(float(clean_num) * 100)
                if volume == 0:
                    icon = "audio-volume-muted-symbolic"
                elif volume < 33:
                    icon = "audio-volume-low-symbolic"
                elif volume < 66:
                    icon = "audio-volume-medium-symbolic"
                else:
                    icon = "audio-volume-high-symbolic"
            except ValueError:
                icon = "audio-volume-muted-symbolic"
        self.sound_image.set_from_icon_name(icon, Gtk.IconSize.MENU)

    def bluetooth_icon_update(self, state):
        if "Powered: yes" in str(state):
            icon = "bluetooth-active-symbolic"
        else:
            icon = "bluetooth-disabled-symbolic"
        self.bluetooth_image.set_from_icon_name(icon, Gtk.IconSize.MENU)

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
                child=Box(
                    orientation="h",
                    spacing=6,
                    children=[icon, Label(label=short_title)]
                ),
                on_clicked=lambda *_, vid=app["id"]: focus_window(vid)
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
    settings_pop = settingspopup()
    my_popup = calendarpopup()
    center_pop = ControlCenterPopup() # Must be fully initialized here!
    apps_pop = AppsPopup()
    launcher_pop = AppLauncherPopup()

    bar = StatusBar(
        calendar_window=my_popup,
        settings_window=settings_pop,
        center_window=center_pop, # Passes the initialized popup into the bar
        apps_window=apps_pop,
        launcher_window=launcher_pop
    )
    
    app = Application("ut-shell", bar, my_popup, settings_pop, center_pop, apps_pop, launcher_pop)
    app.set_stylesheet_from_file(os.path.join(os.path.dirname(__file__), "styles/style.css"))
    app.run()