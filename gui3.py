#!/usr/bin/env python3
import curses
import time
import sys

"""
per-core perf:
#######################################
#######################################
#######################################
#######################################
status
settings
optimization: auto manual
log verbosity: ...
cmd
"""


class Error:
  """ Generic class for all errors of this module. """

class XY:
  def __init__(self, x=0, y=0):
    self.x = x
    self.y = y

  def __add__(self, other):
    return self.__class__(self.x + other.x,
                          self.y + other.y)

  def __sub__(self, other):
    return self.__class__(self.x - other.x,
                          self.y - other.y)

  def __gt__(self, other):
    return self.x > other.x and self.y > other.y

  def __iter__(self):
    return iter([self.x, self.y])


class Area:
  def __init__(self, *args):
    if len(args) == 2:
      self.x1 = args[0].x
      self.y1 = args[0].y
      self.x1 = args[1].x
      self.y2 = args[1].y
    elif len(args) == 4:
      self.x1 = args[0]
      self.y1 = args[1]
      self.x2 = args[2]
      self.y2 = args[3]
    else:
      raise Error("wrong number of arguments")


class Canvas:
  def __init__(self, scr=None, size=XY(80, 24)):
    self._scr = scr
    self._scr.immedok(1)
    self.size = size
    self.pos = XY(0,0)

  def clear(self):
    self._scr.clear()
    # self._scr.refresh()

  def set_pos(self, pos=None):
    if pos:
      self.pos = pos
    self._scr.move(self.pos.y, self.pos.x)

  def printf(self, text, pos=None):
    text = str(text)
    if pos:
      self.set_pos(pos)
    self._scr.addstr(text)
    # self.pos.x += len(text)
    # self.set_p  os()
    # print(text, end='')
    # self._scr.refresh()


class Widget:
  pos = XY(0,0)      # position
  size = XY(0,0)     # actual size
  min_size = XY(1,1) # minimum allowed size
  max_size = None    # maximum allowed size
  can_focus = False  # can widget receive a focus
  focus_order = []
  cur_focus = None   # currently focused widget

  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)
    # assert isinstance(self.canvas, Canvas), "no canvas for %s" % self.__class__
    # assert isinstance(self.size, XY), "no size for %s" % self.__class__
    if self.can_focus:
      self.focus_order.append(self)
      if not Widget.cur_focus:
        Widget.cur_focus = self

  def move_focus(self, inc=1):
    """ Switch focus to next widget. """
    idx = self.focus_order.index(self)
    idx = (idx + inc) % len(self.focus_order)
    widget = self.focus_order[idx]
    Widget.cur_focus = widget
    widget.on_focus()

  def fit(self, pos, max_size):
    """ Request widget to position itself. """
    raise NotImplementedError

  def on_focus(self):
    """ Widget received focus. """

  def draw(self, canvas):
    """ Widget draws itself on canvas. """
    raise NotImplementedError


class VList(Widget):
  def __init__(self, *widgets, **kwargs):
    super().__init__(**kwargs)
    self.widgets = widgets

  def fit(self, pos, max_size, canvas):
    size_x, size_y = 0, 0
    size = XY(size_x, size_y)
    for widget in self.widgets:
      widget.fit(XY(pos.x, size_y), max_size-size, canvas)
      size_x = max(size_x, widget.size.x)
      size_y += widget.size.y
      size = XY(size_x, size_y)
    self.size = size
    self.pos = pos
    self.canvas = canvas

  def draw(self):
    pos = self.pos
    for widget in self.widgets:
      widget.draw()
      pos = pos + XY(0, widget.size.y)


# TODO: clip
class String(Widget):
  def __init__(self, text="", **kwargs):
    super().__init__(**kwargs)
    self.text = text
    self.size = XY(len(text), 1)

  def fit(self, pos, max_size, canvas):
    assert max_size > self.size, "widget does not fit"
    self.pos = pos
    self.canvas = canvas
    return self.size

  def draw(self):
    self.canvas.printf(self.text, self.pos)


class Input(Widget):
  can_focus = True
  min_width = 4
  max_width = 20

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.text = ""

  def fit(self, pos, max_size, canvas):
    self.canvas = canvas
    width = min(self.max_width, max_size.x)
    self.size = XY(width, 1)
    self.pos = pos
    return self.size

  def on_focus(self):
    self.draw()

  def input(self, key):
    if key == 'KEY_UP':
      self.move_focus(-1)
    elif key in ['KEY_DOWN', '\n']:
      self.move_focus(1)
    elif key == '\x7f':
      if self.text:
        self.text = self.text[:-1]
        self.draw()
    if key.isalpha():
      if len(self.text) < self.max_width:
        self.text += key
        self.draw()
    # else:
    #   self.text = "%s %s" %(repr(key),key.isalpha())

  def draw(self):
    self.canvas.printf(' '*self.max_width, self.pos)
    self.canvas.printf(self.text, self.pos)


class Border(Widget):
  def __init__(self, child=None, label="", **kwargs):
    super().__init__(**kwargs)
    self.child = child
    self.label = label

  def fit(self, pos, max_size, canvas):
    label = self.label
    child = self.child
    self.canvas = canvas
    child.fit(pos+XY(1,1), max_size-XY(1,1), canvas)
    self.size  = XY(max(child.size.x, len(label)),
                    child.size.y) + XY(2,2)

  def draw(self):
    pos = self.pos
    canvas = self.canvas
    for y in [pos.y, pos.y+self.size.y-1]:
      for x in range(pos.x+1, pos.x+self.size.x-1):
        canvas.printf('─', pos=XY(x,y))

    for x in [pos.x, pos.x+self.size.x-1]:
      for y in range(pos.y+1, pos.y+self.size.y-1):
        canvas.printf('│', pos=XY(x,y))

    canvas.printf('┌', pos)
    canvas.printf('┐', pos+XY(self.size.x-1, 0))
    canvas.printf('└', pos+XY(0, self.size.y-1))
    canvas.printf('┘', pos+self.size-XY(1,1))

    canvas.printf(self.label, pos+XY(1,0))
    self.child.draw()


def mywrapper(f):
  return lambda *args, **kwargs: curses.wrapper(f, *args, **kwargs)


@mywrapper
def test(scr):
  size_y, size_x = scr.getmaxyx()
  size = XY(size_x, size_y)
  canvas = Canvas(scr, size)
  canvas.clear()

  main = \
    Border(
      VList(
          String("test_string"),
          String("test_string2"),
          Input(),
          Input(),
          Input(),
          ),
      label="test_label")
  main.fit(pos=XY(0,0), max_size=size, canvas=canvas)
  main.draw()

  while True:
    key = scr.getkey()
    Widget.cur_focus.input(key)
    # canvas.printf(repr(key), XY(0,0))



if __name__ == '__main__':
  test()