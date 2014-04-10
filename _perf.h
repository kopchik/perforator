#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include <assert.h>
#include <stdint.h>
#include <sys/ioctl.h>
//#define _GNU_SOURCE
#include <unistd.h>
#include <sys/syscall.h>
#include <err.h>
#include <errno.h>
#include <signal.h>

#include <linux/perf_event.h>


long
perf_event_open(struct perf_event_attr *hw_event, pid_t pid,
                int cpu, int group_fd, unsigned long flags);
