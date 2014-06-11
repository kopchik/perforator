#!/usr/bin/env python3
from perf.lxc import TPL, LXC, NotCountedError

from ipaddress import IPv4Address
from sys import exit
from cmd import Cmd
import argparse

LXC_PREFIX = "/btrfs/"
lxcs = []
vms = []
for x in range(4):
  ip = str(IPv4Address("172.16.5.10")+x)
  name = "perf%s" % x
  lxc = LXC(name=name, root="/btrfs/{}".format(name), tpl="/home/perftemplate/",
            addr=ip, gw="172.16.5.1", cpus=[x])
  lxcs += [lxc]

def callmeth(meth, lxcs):
  for lxc in lxcs:
    getattr(lxc, meth)()

class Mgr(Cmd):
  def do_start(self, arg):
    callmeth('start', lxcs)
  def do_stop(self, arg):
    callmeth('stop', lxcs)
  def do_create(self, arg):
    callmeth('create', lxcs)
  def do_destroy(self, arg):
    callmeth('destroy', lxcs)
  def do_list(self, arg):
    for lxc in lxcs:
      print(lxc)
  def do_quit(self, arg):
    exit()
  do_exit = do_quit


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Control your LXC instances')
  parser.add_argument('-i', '--interactive', default=False, const=True, action='store_const',
      help='launch interactive shell')
  parser.add_argument('cmd', nargs='*')
  args = parser.parse_args()
  print(args)

  mgr = Mgr()
  for cmd in args.cmd:
    mgr.onecmd(cmd)
  if args.interactive:
    mgr.cmdloop()
