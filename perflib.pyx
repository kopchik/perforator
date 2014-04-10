cimport posix.unistd
cdef extern from "linux/perf_event.h":
  ctypedef struct perf_event_attr:
    pass
cdef extern from "_perf.h":
  perf_event_open(perf_event_attr *hw_event, posix.unistd.pid_t pid, int cpu, int group_fd, unsigned long flags)

print ("foobar")
