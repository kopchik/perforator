#!/usr/bin/env python3
import curses
import time
import sys
import math
from functools import total_ordering

# TODO: selectors?

# from useful.log import Log
# log = Log(file=open("/tmp/gui.log", "wt", 2))


def splitline(line, size):
  result = []
  p = 0
  while p < len(line):
    chunk = line[p:p+size]
    result.append(chunk)
    p += size
  return result


class Error:
  """ Generic class for all errors of this module. """


@total_ordering
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

  def __eq__(self, other):
    if not isinstance(other, self.__class__):
      return False
    return self.x == other.x and self.y == other.y

  def __iter__(self):
    return iter([self.x, self.y])

  def __repr__(self):
    cls = self.__class__.__name__
    return "%s(%s, %s)" % (cls, self.x, self.y)


class Canvas:
  def __init__(self, scr=None, size=XY(80, 24)):
    self._scr = scr
    self._scr.immedok(1)
    self.size = size
    self.pos = XY(0,0)

  def clear(self):
    self._scr.clear()
    # self._scr.refresh()

  def curs_set(self, lvl):
    """ Set cursor visibility. """
    curses.curs_set(lvl)

  def set_pos(self, pos=None):
    if pos:
      self.pos = pos
    self._scr.move(self.pos.y, self.pos.x)

  def printf(self, text, pos=None):
    text = str(text)
    if pos:
      self.set_pos(pos)
    self._scr.addstr(text)


class Widget:
  pos = XY(0,0)      # position
  size = XY(0,0)     # actual widget size
  can_focus = False  # can widget receive a focus
  id = None          # identificator for selectors
  focus_order = []
  parent = None      # parent widget
  cur_focus = None   # currently focused widget
  canvas = None

  def __init__(self, *children, **kwargs):
    self.children = list(children)
    for child in children:
      child.parent = self
    self.__dict__.update(kwargs)
    if self.can_focus:
      self.focus_order.append(self)
      if not Widget.cur_focus:
        Widget.cur_focus = self

  def init(self, pos, maxsize, canvas):
    self.set_size(maxsize)
    self.set_pos(pos)
    self.set_canvas(canvas)

  def move_focus(self, inc=1):
    """ Switch focus to next widget. """
    idx = self.focus_order.index(self)
    idx = (idx + inc) % len(self.focus_order)
    widget = self.focus_order[idx]
    Widget.cur_focus = widget
    widget.on_focus()

  def set_size(self, maxsize):
    """ Request widget to position itself. """
    raise NotImplementedError

  def set_pos(self, pos=XY(0,0)):
    self.pos = pos

  def set_canvas(self, canvas):
    self.canvas = canvas
    for child in self.children:
      child.set_canvas(canvas)

  def on_focus(self):
    """ Widget received focus. """
    raise NotImplementedError

  def draw(self):
    """ Draw widget on canvas. """
    raise NotImplementedError

  def input(self, key):
    if key == 'KEY_UP':
      self.move_focus(-1)
    elif key in ['KEY_DOWN', '\n']:
      self.move_focus(1)

  def __getitem__(self, id):
    if self.id == id:
      return self
    for child in self.children:
      r = child[id]
      if r:
        return r
    return None


class VList(Widget):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def set_pos(self, pos):
    self.pos = pos
    size_y = 0
    for child in self.children:
      child_pos = XY(pos.x, pos.y+size_y)
      child.set_pos(child_pos)
      size_y += child.size.y

  def set_size(self, maxsize):
    size_x, size_y = 0, 0
    size = XY(size_x, size_y)
    for child in self.children:
      child.set_size(maxsize-size)
      size_x = max(size_x, child.size.x)
      size_y += child.size.y
      size = XY(size_x, size_y)
    self.size = size
    return self.size

  def draw(self):
    pos = self.pos
    for widget in self.children:
      widget.draw()
      pos = pos + XY(0, widget.size.y)


# TODO: clip
class String(Widget):
  def __init__(self, text="", **kwargs):
    super().__init__(**kwargs)
    self.text = text
    self.size = XY(len(text), 1)

  def set_size(self, maxsize):
    assert self.size <= maxsize, "widget does not fit"
    return self.size

  def draw(self):
    self.canvas.printf(self.text[:self.size.x], self.pos)


class Button(String):
  can_focus = True

  def __init__(self, text='OK!', cb=None, **kwargs):
    super().__init__(**kwargs)
    self.size = XY(len(text)+2, 1)
    self.text = text
    self.has_focus = False
    self.cb = cb

  def on_focus(self):
    self.has_focus = True
    self.draw()
    self.canvas.curs_set(0)

  def on_click(self):
    if self.cb:
      self.cb()

  def input(self, key):
    if key == 'KEY_UP':
      self.has_focus = False
      self.draw()
      self.move_focus(-1)
    elif key in ['KEY_DOWN']:
      self.has_focus = False
      self.draw()
      self.move_focus(1)
    elif key == '\n':
      self.on_click()

  def draw(self):
    if self.has_focus:
      text = '█%s█' % self.text
    else:
      text = ' %s ' % self.text
    self.canvas.printf(text, self.pos)


class Text(Widget):
  size = XY(40, 20)

  def __init__(self, **kwargs):
    self.lines = []
    super().__init__(**kwargs)

  def set_size(self, maxsize):
    assert self.size <= maxsize
    return self.size

  def draw(self):
    result = []
    for line in self.lines:
      chunks = splitline(line, self.size.x)
      result.extend(chunks)

    visible = result[-self.size.y:]

    for i, line in enumerate(visible):
      pos = self.pos+XY(0,i)
      self.canvas.printf(" "*self.size.x, pos)
      self.canvas.printf(line, pos)

  def println(self, s):
    self.lines.append(str(s))
    self.draw()

  def clear(self):
    self.lines = []
    self.draw()


class Input(Widget):
  can_focus = True
  min_width = 4
  max_width = 20

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.text = ""

  def set_size(self, maxsize):
    width = min(self.max_width, maxsize.x)
    self.size = XY(width, 1)
    return self.size

  def on_focus(self):
    self.canvas.curs_set(1)
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
    if key.isalnum():
      if len(self.text) < self.max_width:
        self.text += key
        self.draw()
    # else:
    #   self.text = "%s %s" %(repr(key),key.isalpha())

  def draw(self):
    self.canvas.printf(' '*self.max_width, self.pos)
    self.canvas.printf(self.text, self.pos)


class CMDInput(Input):
  def __init__(self, cb=None, **kwargs):
    super().__init__(**kwargs)
    self.text = ""
    self.cb = cb

  def input(self, key):
    if key == '\n':
      if self.cb:
        self.cb(self.text)
      self.text = ''
      self.draw()
    else:
      super().input(key)


class Border(Widget):
  def __init__(self, *args, label="", **kwargs):
    super().__init__(*args, **kwargs)
    self.label = label

  def set_size(self, maxsize):
    label = self.label
    child = self.children[0]
    child.set_size(maxsize-XY(2,2))
    self.size  = XY(max(child.size.x, len(label)),
                    child.size.y) + XY(2,2)
    return self.size

  def set_pos(self, pos):
    super().set_pos(pos)
    self.children[0].set_pos(pos+XY(1,1))

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
    self.children[0].draw()


class Bars(Widget):
  def __init__(self, data=[0], **kwargs):
    super().__init__(**kwargs)
    self.num = len(data)
    self.data = data

  def set_size(self, maxsize):
    size_y = self.num
    size_x = maxsize.x
    self.size = XY(size_x, size_y)
    return self.size

  def update(self, data):
    self.data = data
    self.draw()

  def draw(self):
    width = self.size.x
    for i, datum in enumerate(self.data):
      pos_x = self.pos.x
      pos_y = self.pos.y + i
      bar = "█" * math.ceil(width*datum)
      self.canvas.printf(bar, XY(pos_x, pos_y))


def mywrapper(f):
  return lambda *args, **kwargs: curses.wrapper(f, *args, **kwargs)


@mywrapper
def gui(scr):
  size_y, size_x = scr.getmaxyx()
  size = XY(size_x, size_y)
  canvas = Canvas(scr, size)
  canvas.clear()

  root = \
    Border(
      VList(
          String("test_string"),
          String("test_string2"),
          Border(Bars([0.01,0.5, 0.7, 1])),
          Border(
                 Text(size=XY(70,8), id='logwin'),
                 label="Logs"),
          CMDInput(id='cmdinpt'),
          Button("QUIT", cb=sys.exit),
          ),
      label="test_label")


  logwin = root['logwin']
  def cb(s):
    tstamp = time.strftime("%H:%M:%S", time.localtime())
    logwin.println("{} {}".format(tstamp, s))
  root['cmdinpt'].cb = cb


  root.init(pos=XY(0,0), maxsize=size, canvas=canvas)
  root.draw()

  if Widget.cur_focus:
    Widget.cur_focus.on_focus()
  while True:
    key = scr.getkey()
    if key == '\x1b':
      break
    if Widget.cur_focus:
      Widget.cur_focus.input(key)
    # canvas.printf(repr(key), XY(0,0))


if __name__ == '__main__':
  gui()
