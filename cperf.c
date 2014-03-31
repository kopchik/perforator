#include <stdlib.h>
#include <strings.h>
#include <assert.h>
#include <stdint.h>
#include <sys/ioctl.h>
#define _GNU_SOURCE
#include <unistd.h>
#include <sys/syscall.h>

#include <linux/perf_event.h>


static long
perf_event_open(struct perf_event_attr *hw_event, pid_t pid,
                int cpu, int group_fd, unsigned long flags)
{
    int ret;

    ret = syscall(__NR_perf_event_open, hw_event, pid, cpu,
                   group_fd, flags);
    return ret;
}

void* mymalloc(size_t size) {
  void* ptr = malloc(size);
  assert(ptr);
  bzero(ptr, size);
  return ptr;
}

int main(void) {
  struct perf_event_attr *pe;
  size_t pe_size = sizeof(struct perf_event_attr);;
  int fd, r;
  pe = mymalloc(sizeof(pe_size));

  pe->size = pe_size;
  pe->type = PERF_TYPE_HARDWARE;
  pe->config = PERF_COUNT_HW_INSTRUCTIONS;
  fd = perf_event_open(pe,  // counter
                        0,   // pid
                        -1,  // cpu
                        -1,  // group_fd
                        0);  // flags

  ioctl(fd, PERF_EVENT_IOC_RESET, 0);
  r = read(fd, &pe, sizeof(long long));
  assert(r>0);

  return 0;
}
