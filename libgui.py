#!/usr/bin/env python3

from functools import total_ordering
import curses
import signal
import math


def splitline(line, size):
  """ Chop line into chunks of specified size. """
  result = []
  ptr = 0
  while ptr < len(line):
    chunk = line[ptr:ptr+size]
    result.append(chunk)
    ptr += size
  return result


class Error(Exception):
  """ Generic class for all errors of this module. """


class NoSpace(Error):
  """ Not enough space to display widget. """


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

  def __ge__(self, other):
    return self.x >= other.x and self.y >= other.y

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
    self.pos = XY(0, 0)

  def curs_set(self, lvl):
    """ Set cursor visibility. """
    curses.curs_set(lvl)

  def set_pos(self, pos=None):
    assert XY(0, 0) <= pos < self.size
    if pos:
      self.pos = pos
    self._scr.move(self.pos.y, self.pos.x)

  def resize(self):
    curses.endwin()
    curses.initscr()
    size_y, size_x = self._scr.getmaxyx()
    self.size = XY(size_x, size_y)
    return self.size

  def clear(self):
    self._scr.erase()

  def printf(self, text, pos=None):
    text = str(text)
    if pos:
      self.set_pos(pos)
    self._scr.addstr(text)


fixed = 0
horiz = 1
vert = 2
both = 3


class Widget:
  pos = XY(0, 0)      # position
  size = XY(0, 0)     # actual widget size calculated in set_size
  minsize = XY(1, 1)  # minimum size for stretching widgets
  stretch = horiz     # widget size policy
  id = None           # ID that can be selected
  all_ids = []        # used for checking ID uniqueness
  can_focus = False   # widget can receive a focus
  focus_order = []
  parent = None       # parent widget
  cur_focus = None    # currently focused widget
  canvas = None       # where all widgets draw themselves
  stretch = horiz

  def __init__(self, *children, **kwargs):
    self.children = list(children)
    for child in children:
      if child.id:
        if child.id in self.all_ids:
          raise Exception("duplicate ID \"%s\", "
                          "IDs must be unique" % child.id)
        self.all_ids.append(child.id)
      child.parent = self
    self.__dict__.update(kwargs)
    if self.can_focus:
      self.focus_order.append(self)
      if not Widget.cur_focus:
        Widget.cur_focus = self

  # TODO: better name
  def init(self, pos, maxsize, canvas=None):
    self.set_size(maxsize)
    self.set_pos(pos)
    if canvas:
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
    if self.minsize and self.minsize >= maxsize:
      raise NoSpace("{}: min size: {}, available: {}"
                    .format(self, self.minsize, maxsize))
    if self.stretch == both:
      self.size = maxsize
    elif self.stretch == horiz:
      self.size = XY(maxsize.x, self.minsize.y)
    elif self.stretch == vert:
      self.size = XY(self.minsize.x, maxsize.y)
    elif self.stretch == fixed:
      pass  # keep size unchanged
    else:
      raise Exception("unknown stretch policy %s" % self.stretch)
    return self.size

  def set_pos(self, pos=XY(0, 0)):
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

  def on_sigwinch(self, sig, frame):
    size = self.canvas.resize()
    self.canvas.clear()
    self.init(self.pos, size)
    self.draw()
    if self.cur_focus:
      self.cur_focus.on_focus()

  def setup_sigwinch(self):
    # there is no old hanlder, see 'python Issue3949'
    signal.signal(signal.SIGWINCH,
                  self.on_sigwinch)

  def __getitem__(self, id):
    if self.id == id:
      return self
    for child in self.children:
      try:
        return child[id]
      except KeyError:
        pass
    raise KeyError

  def __repr__(self):
    cls = self.__class__.__name__
    if self.id:
      id_ = self.id if self.id else id(self)
    return "<{}@{:x}>".format(cls, id_)


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
      child_maxsize = XY(maxsize.x, maxsize.y-size.y)
      child.set_size(child_maxsize)
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


# TODO: clipping?
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
  minsize = XY(5, 5)
  stretch = horiz

  def __init__(self, **kwargs):
    self.lines = []
    super().__init__(**kwargs)

  # def set_size(self, maxsize):
  #   assert self.size <= maxsize
  #   return self.size

  def draw(self):
    # wrap long lines
    result = []
    for line in self.lines:
      chunks = splitline(line, self.size.x)
      result.extend(chunks)
    # display only visible lines
    visible = result[-self.size.y:]
    for i, line in enumerate(visible):
      pos = self.pos + XY(0, i)
      self.canvas.printf(" "*self.size.x, pos)
      self.canvas.printf(line, pos)

  def println(self, s):
    self.lines.append(str(s))
    self.draw()

  def write(self, s):
    """ This one is just to emulate file API. """
    self.println(s.strip())

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
    assert len(self.children) == 1,  \
        "border fits only one child"
    self.label = label

  def set_size(self, maxsize):
    label = self.label
    child = self.children[0]
    child.set_size(maxsize-XY(2, 2))
    size_x = max(child.size.x, len(label))  # make sure label fits
    size_y = child.size.y
    self.size = XY(size_x, size_y) + XY(2, 2)  # 2x2 is a border
    return self.size

  def set_pos(self, pos):
    super().set_pos(pos)
    child = self.children[0]
    child.set_pos(pos+XY(1, 1))  # 1x1 is offset by border

  def draw(self):
    pos = self.pos
    canvas = self.canvas
    for y in [pos.y, pos.y+self.size.y-1]:
      for x in range(pos.x+1, pos.x+self.size.x-1):
        canvas.printf('─', pos=XY(x, y))

    for x in [pos.x, pos.x+self.size.x-1]:
      for y in range(pos.y+1, pos.y+self.size.y-1):
        canvas.printf('│', pos=XY(x, y))

    canvas.printf('┌', pos)
    canvas.printf('┐', pos+XY(self.size.x-1, 0))
    canvas.printf('└', pos+XY(0, self.size.y-1))
    canvas.printf('┘', pos+self.size-XY(1, 1))

    canvas.printf(self.label, pos+XY(1, 0))
    self.children[0].draw()


class Bars(Widget):
  def __init__(self, data=[0], **kwargs):
    super().__init__(**kwargs)
    self.num = len(data)
    self.data = data

  def set_size(self, maxsize):
    size_x = maxsize.x
    size_y = self.num
    size = XY(size_x, size_y)
    assert size < maxsize
    self.size = size
    return self.size

  def update(self, data):
    self.data = data
    self.draw()

  def draw(self):
    width = self.size.x
    for i, datum in enumerate(self.data):
      pos_x = self.pos.x
      pos_y = self.pos.y + i
      bar = "█" * math.ceil(width*min(datum,1.0))
      self.canvas.printf(bar, XY(pos_x, pos_y))


def mywrapper(f):
  return lambda *args, **kwargs: curses.wrapper(f, *args, **kwargs)
