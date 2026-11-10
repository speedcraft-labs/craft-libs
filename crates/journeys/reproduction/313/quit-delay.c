/* Test-only shutdown delay. Loaded only into the two validation app processes.
 * Both arms use this library; only the treatment arm has a nonzero delay.
 * Never used for production comparison or calibration. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static uint64_t ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) _exit(117);
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
__attribute__((destructor)) static void delay_quit(void) {
    const char *value = getenv("CRAFT_JOURNEYS_TEST_QUIT_DELAY_NS");
    const char *path = getenv("CRAFT_JOURNEYS_TEST_QUIT_DELAY_LOG");
    if (!value || !path) return;
    char *end;
    errno = 0;
    uint64_t requested = strtoull(value, &end, 10);
    if (errno || *end || requested > 1000000000ULL) _exit(118);
    uint64_t started = ns(), deadline = started + requested;
    struct timespec until = {(time_t)(deadline / 1000000000ULL), (long)(deadline % 1000000000ULL)};
    int status = 0;
    if (requested) do { status = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &until, NULL); } while (status == EINTR);
    uint64_t ended = ns();
    if (status) _exit(119);
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (fd < 0) _exit(120);
    char row[256];
    int count = snprintf(row, sizeof(row), "{\"pid\":%ld,\"requested_ns\":%" PRIu64 ",\"started_ns\":%" PRIu64 ",\"ended_ns\":%" PRIu64 ",\"actual_delay_ns\":%" PRIu64 "}\n", (long)getpid(), requested, started, ended, ended-started);
    if (count <= 0 || count >= (int)sizeof(row) || write(fd, row, (size_t)count) != count || close(fd)) _exit(121);
}
