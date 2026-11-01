/* Linux-only contained birth. No Python, allocation or stdio in the child.
 * This is a host primitive, not authentication, a sandbox or a launch grant.
 */
#define _GNU_SOURCE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/close_range.h>
#include <linux/magic.h>
#include <linux/sched.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

struct mapping {
  int target;
  int original;
  int source;
};

static void free_vector(char **v) {
  if (v) {
    for (size_t i = 0; v[i]; ++i)
      free(v[i]);
    free(v);
  }
}

static char *copy_text(PyObject *value) {
  Py_ssize_t size;
  if (!PyUnicode_Check(value)) {
    PyErr_SetString(PyExc_TypeError, "Process arguments must be strings");
    return NULL;
  }
  const char *s = PyUnicode_AsUTF8AndSize(value, &size);
  if (!s)
    return NULL;
  if (memchr(s, 0, (size_t)size)) {
    PyErr_SetString(PyExc_ValueError, "NUL in process argument");
    return NULL;
  }
  char *result = strdup(s);
  if (!result)
    PyErr_NoMemory();
  return result;
}

static int native_fd(PyObject *v, int maximum) {
  if (!PyLong_CheckExact(v)) {
    PyErr_SetString(PyExc_TypeError, "Expected an integer file descriptor");
    return -1;
  }
  long fd = PyLong_AsLong(v);
  if (fd == -1 && PyErr_Occurred())
    return -1;
  if (fd < 0 || fd > maximum) {
    PyErr_SetString(PyExc_ValueError, "File descriptor out of bounds");
    return -1;
  }
  return (int)fd;
}

static int check_cgroup(int fd) {
  struct statfs info;
  if (fstatfs(fd, &info) < 0)
    return -1;
  if ((unsigned long)info.f_type != CGROUP2_SUPER_MAGIC) {
    errno = EINVAL;
    return -1;
  }
  return 0;
}

static void child_error(int fd, int number) {
  const char *p = (const char *)&number;
  size_t offset = 0;
  while (offset < sizeof(number)) {
    ssize_t n = write(fd, p + offset, sizeof(number) - offset);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0)
      break;
    offset += (size_t)n;
  }
  _exit(127);
}

static pid_t execute_into(int cg_copy, char **argv, char **env,
                          struct mapping *maps, Py_ssize_t count, int read_fd,
                          int *error_fd, int *pidfd) {
  sigset_t all, old;
  sigfillset(&all);
  int mask_error = pthread_sigmask(SIG_SETMASK, &all, &old);
  if (mask_error) {
    errno = mask_error;
    return -1;
  }
  struct clone_args options = {0};
  options.flags = CLONE_INTO_CGROUP | CLONE_PIDFD;
  options.pidfd = (uint64_t)(uintptr_t)pidfd;
  options.exit_signal = SIGCHLD;
  options.cgroup = (uint64_t)cg_copy;
  pid_t pid = (pid_t)syscall(SYS_clone3, &options, sizeof(options));
  int saved = errno;
  if (pid == 0) {
    /* Child: only signal-safe native operations until execve/_exit. */
    if (syscall(SYS_close_range, 3U, ~0U, CLOSE_RANGE_CLOEXEC) < 0)
      child_error(*error_fd, errno);
    for (Py_ssize_t m = 0; m < count; ++m)
      if (dup2(maps[m].source, maps[m].target) < 0)
        child_error(*error_fd, errno);
    struct sigaction action = {0};
    action.sa_handler = SIG_DFL;
    sigemptyset(&action.sa_mask);
    for (int sig = 1; sig < NSIG; ++sig) {
      if (sig == SIGKILL || sig == SIGSTOP)
        continue;
      if (sigaction(sig, &action, NULL) < 0 && errno != EINVAL)
        child_error(*error_fd, errno);
    }
    sigset_t empty;
    sigemptyset(&empty);
    if (sigprocmask(SIG_SETMASK, &empty, NULL) < 0)
      child_error(*error_fd, errno);
    execve(argv[0], argv, env);
    child_error(*error_fd, errno);
  }
  (void)pthread_sigmask(SIG_SETMASK, &old, NULL);
  if (pid < 0) {
    errno = saved;
    return -1;
  } /* No fallback to spawning then moving a PID. */
  saved = 0;
  close(*error_fd);
  *error_fd = -1;
  int exec_error = 0;
  size_t received = 0;
  while (received < sizeof(exec_error)) {
    ssize_t n = read(read_fd, (char *)&exec_error + received,
                     sizeof(exec_error) - received);
    if (n < 0 && errno == EINTR)
      continue;
    if (n < 0) {
      saved = errno;
      break;
    }
    if (n == 0)
      break;
    received += (size_t)n;
  }
  if (received || saved) {
    if (!saved)
      saved = received == sizeof(exec_error) ? exec_error : EIO;
    (void)syscall(SYS_pidfd_send_signal, *pidfd, SIGKILL, NULL, 0);
    while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {
    }
    errno = saved;
    return -1;
  }
  return pid;
}

static PyObject *spawn(PyObject *self, PyObject *args) {
  (void)self;
  PyObject *cg, *argv_obj, *env_obj, *fds_obj, *fast = NULL;
  char **argv = NULL, **env = NULL;
  struct mapping *maps = NULL;
  Py_ssize_t count = 0, position = 0, total = 0;
  int cg_copy = -1, pipes[2] = {-1, -1}, error_fd = -1;
  int pidfd = -1, saved = 0, maximum = 2, standard = 0;
  pid_t pid = -1;
  PyObject *result = NULL;
  if (!PyArg_ParseTuple(args, "OOOO:spawn", &cg, &argv_obj, &env_obj, &fds_obj))
    return NULL;
  int cg_fd = native_fd(cg, INT_MAX);
  if (cg_fd < 0)
    return NULL;
  if (check_cgroup(cg_fd) < 0)
    return PyErr_SetFromErrno(PyExc_OSError);
  if (!PyDict_Check(env_obj) || !PyDict_Check(fds_obj)) {
    PyErr_SetString(PyExc_TypeError,
                    "Expected explicit environment and FD mappings");
    return NULL;
  }
  fast = PySequence_Fast(argv_obj, "Expected process argument sequence");
  if (!fast)
    goto done;
  total = PySequence_Fast_GET_SIZE(fast);
  if (total < 1 || total > 4096 || PyDict_Size(env_obj) > 4096 ||
      PyDict_Size(fds_obj) > 4096) {
    PyErr_SetString(PyExc_ValueError, "Process specification exceeds bounds");
    goto done;
  }
  argv = calloc((size_t)total + 1, sizeof(char *));
  env = calloc((size_t)PyDict_Size(env_obj) + 1, sizeof(char *));
  count = PyDict_Size(fds_obj);
  maps = calloc((size_t)count + 1, sizeof(struct mapping));
  if (!argv || !env || !maps) {
    PyErr_NoMemory();
    goto done;
  }
  for (Py_ssize_t i = 0; i < count; ++i)
    maps[i].source = -1;
  for (Py_ssize_t i = 0; i < total; ++i) {
    argv[i] = copy_text(PySequence_Fast_GET_ITEM(fast, i));
    if (!argv[i])
      goto done;
  }
  if (argv[0][0] != '/') {
    PyErr_SetString(PyExc_ValueError, "Executable must be absolute");
    goto done;
  }
  PyObject *key, *value;
  Py_ssize_t i = 0;
  while (PyDict_Next(env_obj, &position, &key, &value)) {
    char *k = copy_text(key), *v = NULL;
    if (!k)
      goto done;
    if (!*k || strchr(k, '=')) {
      free(k);
      PyErr_SetString(PyExc_ValueError, "Invalid environment key");
      goto done;
    }
    v = copy_text(value);
    if (!v) {
      free(k);
      goto done;
    }
    size_t n = strlen(k) + strlen(v) + 2;
    env[i] = malloc(n);
    if (!env[i]) {
      free(k);
      free(v);
      PyErr_NoMemory();
      goto done;
    }
    memcpy(env[i], k, strlen(k));
    env[i][strlen(k)] = '=';
    memcpy(env[i] + strlen(k) + 1, v, strlen(v) + 1);
    free(k);
    free(v);
    ++i;
  }
  position = 0;
  i = 0;
  while (PyDict_Next(fds_obj, &position, &key, &value)) {
    int target = native_fd(key, 4096), source = native_fd(value, INT_MAX);
    if (target < 0 || source < 0)
      goto done;
    if (target > maximum)
      maximum = target;
    if (target < 3)
      standard |= 1 << target;
    maps[i].target = target;
    maps[i].original = source;
    ++i;
  }
  if (standard != 7) {
    PyErr_SetString(PyExc_ValueError,
                    "All standard descriptors require explicit mappings");
    goto done;
  }
  /* Duplicate every source above all destinations before any remapping. */
  for (i = 0; i < count; ++i) {
    int source = maps[i].original;
    int copy = fcntl(source, F_DUPFD_CLOEXEC, maximum + 1);
    if (copy < 0) {
      saved = errno;
      goto done;
    }
    maps[i].source = copy;
  }
  cg_copy = fcntl(cg_fd, F_DUPFD_CLOEXEC, maximum + 1);
  if (cg_copy < 0 || pipe2(pipes, O_CLOEXEC) < 0) {
    saved = errno;
    goto done;
  }
  error_fd = fcntl(pipes[1], F_DUPFD_CLOEXEC, maximum + 1);
  if (error_fd < 0) {
    saved = errno;
    goto done;
  }
  close(pipes[1]);
  pipes[1] = -1;
  Py_BEGIN_ALLOW_THREADS pid = execute_into(cg_copy, argv, env, maps, count,
                                            pipes[0], &error_fd, &pidfd);
  saved = errno;
  Py_END_ALLOW_THREADS if (pid < 0) goto done;
  saved = 0;
  result = Py_BuildValue("ii", (int)pid, pidfd);
  if (result)
    pidfd = -1; /* Transfer ownership only after Python allocation. */
  else {
    (void)syscall(SYS_pidfd_send_signal, pidfd, SIGKILL, NULL, 0);
    while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {
    }
  }
done:
  if (cg_copy >= 0)
    close(cg_copy);
  if (error_fd >= 0)
    close(error_fd);
  if (pidfd >= 0)
    close(pidfd);
  if (pipes[0] >= 0)
    close(pipes[0]);
  if (pipes[1] >= 0)
    close(pipes[1]);
  if (maps) {
    for (i = 0; i < count; ++i)
      if (maps[i].source > maximum)
        close(maps[i].source);
    free(maps);
  }
  free_vector(argv);
  free_vector(env);
  Py_XDECREF(fast);
  if (saved && !PyErr_Occurred()) {
    errno = saved;
    PyErr_SetFromErrno(PyExc_OSError);
  }
  return result;
}

static PyObject *validate(PyObject *self, PyObject *arg) {
  (void)self;
  int fd = native_fd(arg, INT_MAX);
  if (fd < 0)
    return NULL;
  if (check_cgroup(fd) < 0)
    return PyErr_SetFromErrno(PyExc_OSError);
  Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {"spawn", spawn, METH_VARARGS,
     "Create directly in a cgroup; explicit argv/env/FD map."},
    {"validate", validate, METH_O, "Reject non-cgroup2 descriptors."},
    {NULL, NULL, 0, NULL}};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT,
                                    "_domain_spawn",
                                    NULL,
                                    -1,
                                    methods,
                                    NULL,
                                    NULL,
                                    NULL,
                                    NULL};
PyMODINIT_FUNC PyInit__domain_spawn(void) { return PyModule_Create(&module); }
