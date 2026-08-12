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

class StatusBar(Window):
    def __init__(self, calendar_window, **kwargs):
        super().__init__(
            layer="top",
            anchor="left top right",
            exclusivity="auto",
            **kwargs
        )

        self.wifi_label = Label(label="WiFi: --")
        self.wifi_fabricator = Fabricator(
            poll_from=lambda *_: os.popen("nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes' | cut -d: -f2").read().strip() 
            if os.system("which nmcli > /dev/null 2>&1") == 0 
            else "N/A", interval=5000
        ).build().connect("changed", lambda _, val: self.wifi_label.set_label(f"WiFi: {val}")).unwrap()


        self.date_button = Button(
            label="Date: --",
            on_enter_notify_event=lambda *_: calendar_window.show_all(),
            on_leave_notify_event=lambda *_: calendar_window.hide()
        )




        
        self.clock_label = Label(label="--:--:--")
        self.clock_fabricator = Fabricator(
            poll_from=lambda *_: time.strftime("%I:%M:%S %p"), interval=1000
        ).build().connect("changed", lambda _, val: self.clock_label.set_label(f"{val}")).unwrap()





        
        self.battery_label = Label(label="Battery: --%")
        self.battery_fabricator = Fabricator(
            poll_from=lambda *_: open("/sys/class/power_supply/BAT1/capacity").read().strip() 
            if os.path.exists("/sys/class/power_supply/BAT1/capacity") 
            else "N/A", interval=5000
        ).build().connect("changed", lambda _, val: self.battery_label.set_label(f"Battery: {val}%")).unwrap()




        self.sound_label = Label(label="volume: --%")
        self.sound_fabricator = Fabricator(
            # Polls the native WirePlumber command
            poll_from=lambda *_: os.popen("wpctl get-volume @DEFAULT_AUDIO_SINK@").read().strip().replace("Volume: ", ""), 
            interval=500
        ).build().connect("changed", lambda _, val: self.sound_label.set_label(f"Vol: {val}")).unwrap()




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
            children=[self.clock_label,
            self.battery_label, self.sound_label, self.wifi_label]
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
    my_popup = calendarpopup()
    bar = StatusBar(calendar_window=my_popup)
    app = Application("ut-shell", bar, my_popup)
    app.run()