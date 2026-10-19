"""A recording stand-in for tkinter, so the window can be built without a display.

It is only accurate enough to run `app.main()` and fire the callbacks it wires up.
Option names are not validated, so this proves the Python wiring, not the Tk layout.
"""


class Var:
    def __init__(self, value=None, **_options):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class StringVar(Var):
    def __init__(self, value="", **options):
        super().__init__(value, **options)


class BooleanVar(Var):
    def __init__(self, value=False, **options):
        super().__init__(value, **options)


class Widget:
    def __init__(self, master=None, **options):
        self.master = master
        self.options = dict(options)
        self.visible = False
        self.binds = {}
        root(self).record(self)

    def pack(self, **_options):
        self.visible = True

    def pack_forget(self):
        self.visible = False

    def grid(self, **_options):
        self.visible = True

    def configure(self, **options):
        self.options.update(options)

    config = configure

    def bind(self, sequence, func):
        self.binds[sequence] = func


def root(widget):
    node = widget
    while getattr(node, "master", None) is not None:
        node = node.master
    return node


class Frame(Widget):
    pass


class Label(Widget):
    pass


class Entry(Widget):
    pass


class Button(Widget):
    def invoke(self):
        self.options["command"]()


class Checkbutton(Widget):
    def toggle(self):
        variable = self.options["variable"]
        variable.set(not variable.get())
        self.options["command"]()


class Text(Widget):
    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.content = ""

    def delete(self, *_args):
        self.content = ""

    def insert(self, _index, text):
        self.content += text

    def get(self, *_args):
        return self.content


class Event:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Canvas(Widget):
    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.items = {}

    def _add(self, kind, coords, options):
        key = len(self.items) + 1
        self.items[key] = {"kind": kind, "coords": coords, **options}
        return key

    def create_rectangle(self, *coords, **options):
        return self._add("rectangle", coords, options)

    def create_oval(self, *coords, **options):
        return self._add("oval", coords, options)

    def itemconfigure(self, key, **options):
        self.items[key].update(options)

    def canvasx(self, value):
        return value

    def canvasy(self, value):
        return value

    def click(self, x, y):
        self.binds["<Button-1>"](Event(x, y))
        self.binds["<ButtonRelease-1>"](Event(x, y))

    def drag(self, x, y):
        self.binds["<B1-Motion>"](Event(x, y))

    def hover(self, x, y):
        self.binds["<Motion>"](Event(x, y))


instances = []


class Tk(Widget):
    def __init__(self):
        self.widgets = []
        super().__init__(None)
        self.clipboard = ""
        self.ran = False
        instances.append(self)

    def record(self, widget):
        self.widgets.append(widget)

    def title(self, _text):
        pass

    def mainloop(self):
        self.ran = True

    def after(self, _delay, func):
        func()

    def clipboard_clear(self):
        self.clipboard = ""

    def clipboard_append(self, text):
        self.clipboard += text

    def of_type(self, cls):
        return [widget for widget in self.widgets if type(widget) is cls]

    def button(self, text):
        for widget in self.of_type(Button):
            if widget.options.get("text") == text:
                return widget
        raise KeyError(text)
