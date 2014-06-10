#!/usr/bin/env python3
from ipaddress import IPv4Address

from perf.lxc import TPL, LXC, NotCountedError
from sys import exit

LXC_PREFIX = "/btrfs/"
lxcs = []
for x in range(1):
  ip = str(IPv4Address("172.16.5.10")+x)
  name = "perf%s" % x
  lxc = LXC(name=name, root="/btrfs/{}".format(name), tpl="/home/perftemplate/",
            addr=ip, gw="172.16.5.1", cpus=[x])
  lxcs += [lxc]
  lxc.stop()
  lxc.destroy()
  lxc.create()

lxc = lxcs[0]
lxc.start()
p = lxc.Popen("burnCortexA9")
for _ in range(10):
  try:
    print("!", lxc.ipcstat(0.2))
  except NotCountedError as err:
    print("EE", err)
p.killall()
lxc.destroy()
