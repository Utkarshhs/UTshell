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
                        
                        # Dynamically ask Linux: "Do you have an icon matching any of these words?"
                        for word in clean_words:
                            if theme.has_icon(word):
                                app_name = word 
                                break
                                
                    if not theme.has_icon(app_name):
                        if "kitty" in app_name.lower():
                            app_name = "utilities-terminal" # The standard Linux terminal icon
                        else:
                            app_name = "application-x-executable" # A clean default gear icon
                            
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

class StatusBar(Window):
    def __init__(self, calendar_window, settings_window, **kwargs):
        super().__init__(
            layer="top",
            anchor="left top right",
            exclusivity="auto",
            **kwargs
        )

        self.wifi_label = Label(label="Wi-Fi: --")
        self.sound_label = Label(label="Vol: --%")
        self.battery_label = Label(label="Battery: --%")
        self.clock_label = Label(label="--:--:--")


        self.info_box = Box(
            orientation="h",
            spacing=10,
            children=[self.wifi_label, self.sound_label, self.battery_label]
        )

        self.system_button = Button(
            child=self.info_box,
            on_clicked=lambda *_: settings_window.show_all() if not settings_window.get_visible() else settings_window.hide()
        )

        self.wifi_fabricator = Fabricator(
            poll_from=lambda *_: os.popen("nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes' | cut -d: -f2").read().strip() 
            if os.system("which nmcli > /dev/null 2>&1") == 0 
            else "N/A", interval=5000
        ).build().connect("changed", lambda _, val: self.wifi_label.set_label(f"Wi-Fi: {val}")).unwrap()

        self.date_button = Button(
            label="Date: --",
            on_clicked=lambda *_: calendar_window.show_all() if not calendar_window.get_visible() else calendar_window.hide()
        )
        
        
        self.clock_fabricator = Fabricator(
            poll_from=lambda *_: time.strftime("%I:%M:%S %p"), interval=1000
        ).build().connect("changed", lambda _, val: self.clock_label.set_label(f"{val}")).unwrap()

        self.battery_fabricator = Fabricator(
            poll_from=lambda *_: open("/sys/class/power_supply/BAT1/capacity").read().strip() 
            if os.path.exists("/sys/class/power_supply/BAT1/capacity") 
            else "N/A", interval=5000
        ).build().connect("changed", lambda _, val: self.battery_label.set_label(f"Battery: {val}%")).unwrap()

        self.sound_fabricator = Fabricator(
            poll_from=lambda *_: os.popen("wpctl get-volume @DEFAULT_AUDIO_SINK@").read().strip().replace("Volume: ", ""), 
            interval=500
        ).build().connect("changed", lambda _, val: self.sound_label.set_label(f"Vol: {float(val) * 100:.0f}%")).unwrap()

        self.date_fabricator = Fabricator(
            poll_from=lambda *_: time.strftime("%a,%b,%d"), interval=6000
        ).build().connect("changed", lambda _, val: self.date_button.set_label(f"{val}")).unwrap()

        self.dock_fabricator = Fabricator(
            poll_from=lambda *_: get_wayfire(),
            interval=50
        ).build().connect("changed", lambda _, val: self.update_taskbar(val))

        self.box1 = Box(
            orientation="h",
            children=[self.date_button, self.clock_label]
        )
        
        self.box2 = Box(
            orientation="h",
            spacing=10,
            children=[self.system_button]
        )
        
        self.app_container = Box(
            name="taskbar",
            orientation="h",
            spacing=10,
            children=[]
        )

        self.main_desktop = Box(
            orientation = "h",
            spacing=10,
            children=[]
        )
        # main left box 
        self.left_box = Box(
            orientation="h",
            spacing=10,
            children=[self.box2,self.app_container]
        )
        
        self.children = CenterBox(
            center_children=self.main_desktop, 
            start_children=self.left_box,
            end_children=self.box1
        )
        self.show_all()

  
    def update_taskbar(self, window_list):
        # 1. Safely purge old buttons (Don't skip this, or icons will duplicate infinitely!)
        for child in self.app_container.get_children():
            self.app_container.remove(child)
            child.destroy()
            
        # 2. Forge new buttons
        for app in window_list:
            icon = Gtk.Image.new_from_icon_name(app['app_id'], Gtk.IconSize.DND)
            icon.set_pixel_size(32) 
            
            btn = Button(
                image=icon,
                tooltip_text=app['title'],
                style="background: transparent; border: none; box-shadow: none;", 
                on_clicked=lambda *_, vid=app['id']: focus_window(vid) 
            )
            
            # 3. THIS IS THE MISSING LINE! Attach the button to the UI
            self.app_container.add(btn)
            
        # 4. Paint the new buttons to the screen
        self.app_container.show_all()

if __name__ == "__main__":
    settings_pop = settingspopup()
    my_popup = calendarpopup()
    bar = StatusBar(calendar_window=my_popup, settings_window=settings_pop)
    app = Application("ut-shell", bar, my_popup, settings_pop)
    app.run()