from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc.stdint cimport uint32_t, uint64_t
from posix.unistd cimport pid_t
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

cdef extern from "_perf.h":
  void* mymalloc(size_t size)
  perf_event_open(perf_event_attr *event, pid_t pid,
                  int cpu, int group_fd, unsigned long flags)


cdef class Task:
  cdef pid_t pid
  def __cinit__(self, pid_t pid=0):
    cdef int fd, pe_size
    cdef perf_event_attr *pe

    os.kill(pid, 0)
    self.pid = pid

    pe_size = sizeof(perf_event_attr)
    pe = <perf_event_attr*>mymalloc(pe_size)
    pe.size = pe_size
    pe.type = PERF_TYPE_HARDWARE
    pe.disabled = 1
    pe.config = PERF_COUNT_HW_INSTRUCTIONS
    fd = perf_event_open(pe, pid, -1, -1, 0)
    # TODO: free mem
    print("OPA")