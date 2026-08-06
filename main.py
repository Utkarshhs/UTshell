import fabric # importing the base package
from fabric import Application
from fabric.widgets.box import Box # grabs the Box class from Fabric
from fabric.widgets.label import Label # gets the Label class
from fabric.widgets.window import Window # grabs the Window class from Fabric
from fabric.widgets.button import Button # grabs the Button class from Fabric
from fabric.widgets.datetime import DateTime
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window  # Replace the previous Window import with this

def create_button():
    return Button(label="Click me!", on_clicked=lambda b, *_: b.set_label("button clicked!"))

if __name__ == "__main__":
    box1 = Box(
        orientation="v",
        children=[
            Label(label="fabric button example"),
            Box(orientation="h",
                children=[create_button(),
                          create_button(),
                          create_button(),
                ]
            ),
        
      
    Label(label="This is the first box."),
    Label(label="This is the second box."),
        ]
    )
    box_2 = Box(
        spacing=20,
        orientation="h",
        children=[
            Label(label="this is the first element in the second box"),
            Label(label="this is the second element in the second box"),
        ]
    )

    box1.add(box_2) # add box_2 to box1
    window = Window(child=box1) # create a window with box1 as its child
    app = Application("default", window) # define a new config named "default" which holds `window`
    app.run() # run the event loop (run the config)