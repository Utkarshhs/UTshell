import time
import os
import fabric
from fabric import Application, Fabricator
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from fabric.widgets.eventbox import EventBox
from fabric.widgets.revealer import Revealer

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
        self.wifi_expand_button = Button(label = "⌄")
        self.wifi_expand_button.connect("clicked", lambda *_: [self.scan_networks(), self.wifi_revealer.set_reveal_child(not self.wifi_revealer.get_reveal_child())])
        self.wifi_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.handler_box = Box(orientation="v",  spacing=5,)
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
        for child in self.handler_box.get_children():
            self.handler_box.remove(child)
            child.destroy()
        for network in networks:
            button = Button(label=network, on_clicked=lambda *_, target=network: os.system(f"nmcli dev wifi connect '{target}'"))
            self.handler_box.add(button)
        self.handler_box.show_all()


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
        
        self.clock_label = Label(label="--:--:--")
        
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

        self.box1 = Box(
            orientation="h",
            children=[self.date_button]
        )
        
        self.box2 = Box(
            orientation="h",
            spacing=10,
            children=[self.system_button, self.clock_label]
        )
        
        self.app_container = Box(
            name="taskbar",
            orientation="h",
            spacing=10,
            children=[]
        )
        
        self.children = CenterBox(
            center_children=self.app_container, 
            start_children=self.box2, 
            end_children=self.box1
        )
        self.show_all()

if __name__ == "__main__":
    settings_pop = settingspopup()
    my_popup = calendarpopup()
    bar = StatusBar(calendar_window=my_popup, settings_window=settings_pop)
    app = Application("ut-shell", bar, my_popup, settings_pop)
    app.run()