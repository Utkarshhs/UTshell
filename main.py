import fabric # importing the base package
import time
from fabric import Application , Fabricator
from fabric.widgets.box import Box # grabs the Box class from Fabric
from fabric.widgets.label import Label # gets the Label class
from fabric.widgets.window import Window # grabs the Window class from Fabric
from fabric.widgets.button import Button # grabs the Button class from Fabric
from fabric.widgets.datetime import DateTime
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.core.service import Service, Signal , Property
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import os  # Replace the previous Window import with this

class calendarpopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="top",
            anchor="top right",
            margin=(50,10,10,10),
            visible=False,
            **kwargs
        )
        my_calendar = Gtk.Calendar()
        self.add(my_calendar)
        
class StatusBar(Window):
    def __init__(self,calendar_window, **kwargs):
        super().__init__(
            layer="top",
            anchor="left top right",
            exclusivity="auto",
            **kwargs
        )
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
            else "N/A",interval=1000  # Add the calendar to the window instead of the label
            ).build().connect("changed", lambda _, val: self.battery_label.set_label(f"{val}%")).unwrap()

        self.date_fabricator = Fabricator(
            poll_from=lambda *_: time.strftime("%a,%b,%d"), interval=6000
        ).build().connect("changed", lambda _, val: self.date_button.set_label(f"{val}")).unwrap() 

        self.box1 = Box(
                    orientation="h",                    
                            children=[
                                self.date_button
                            ]
                        ),

        self.box2 = Box(
                    orientation="h",
                    spacing=10,
                    children=[
                        self.clock_label,
                    ]
                )
        self.children = CenterBox(center_children=self.battery_label,start_children=self.box2 , end_children=self.box1) 


if __name__ == "__main__":
    my_popup = calendarpopup()
    bar = StatusBar(calendar_window=my_popup)
    app = Application("ut-shell", bar, my_popup) # define a new config named "default" which holds `window`
    app.run() # run the event loop (run the config)