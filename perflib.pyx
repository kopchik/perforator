from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc.stdint cimport int64_t, uint32_t, uint64_t
from posix.unistd cimport pid_t, useconds_t, read, usleep
from posix.ioctl cimport ioctl
from cython cimport sizeof
import os

cdef extern from "linux/perf_event.h":
  cdef struct perf_event_attr:
    uint32_t type
    uint32_t size
    uint64_t config
    uint64_t disabled
  cdef enum perf_type_id:
    PERF_TYPE_HARDWARE
    PERF_COUNT_HW_INSTRUCTIONS
  cdef int PERF_EVENT_IOC_RESET

cdef extern from "_perf.h":
  void* mymalloc(size_t size)
  int perf_event_open(perf_event_attr *event, pid_t pid,
                  int cpu, int group_fd, unsigned long flags)

  
cdef class Task:
  cdef pid_t pid
  cdef int fd

  def __cinit__(self, pid_t pid=0):
    cdef int fd, pe_size
    cdef perf_event_attr *pe

    os.kill(pid, 0)
    self.pid = pid

    pe_size = sizeof(perf_event_attr)
    pe = <perf_event_attr*>mymalloc(pe_size)
    pe.size = pe_size
    pe.type = PERF_TYPE_HARDWARE
    pe.disabled = 0
    pe.config = PERF_COUNT_HW_INSTRUCTIONS
    fd = perf_event_open(pe, pid, -1, -1, 0)
    assert fd, "failed to open fd"
    self.fd = fd

  def measure(self, double interval):
    cdef int r
    cdef uint64_t cnt
    r = ioctl(self.fd, PERF_EVENT_IOC_RESET, 0)
    assert r != -1, "ioctl PERF_EVENT_IOC_RESET failed"
    usleep(<useconds_t>interval*(10**6))  # convert seconds to microseconds
    r = read(self.fd, &cnt, sizeof(cnt))
    assert r != -1
    return cnt
  def measurex(self, double interval, int num):
    cdef uint64_t r[num]
    for x in range(num):
      r[num] = x
    return r