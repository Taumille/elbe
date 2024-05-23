# ELBE - Debian Based Embedded Rootfilesystem Builder
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2014-2017 Linutronix GmbH
# SPDX-FileCopyrightText: 2014 Ferdinand Schwenk <ferdinand.schwenk@emtrion.de>

import contextlib
import logging
import os
import shlex
import subprocess

from elbepack.log import async_logging_ctx


"""
Forward to elbe logging system.
"""
ELBE_LOGGING = object()


def _is_shell_cmd(cmd):
    return isinstance(cmd, str)


def _log_cmd(cmd):
    if _is_shell_cmd(cmd):
        return cmd
    else:
        return shlex.join(map(os.fspath, cmd))


def run(cmd, /, *, check=True, log_cmd=None, **kwargs):
    """
    Like subprocess.run() but
     * defaults to check=True
     * logs the executed command
     * accepts ELBE_LOGGING for stdout and stderr

    --

    Let's quiet the loggers

    >>> import os
    >>> import sys
    >>> from elbepack.log import open_logging
    >>> open_logging({"files":os.devnull})

    >>> run(['echo', 'ELBE'])
    CompletedProcess(args=['echo', 'ELBE'], returncode=0)

    >>> run(['echo', 'ELBE'], capture_output=True)
    CompletedProcess(args=['echo', 'ELBE'], returncode=0, stdout=b'ELBE\\n', stderr=b'')

    >>> run(['false']) # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: ...

    >>> run('false', check=False).returncode
    1

    >>> run(['cat', '-'], input=b'ELBE', capture_output=True).stdout
    b'ELBE'

    >>> run(['echo', 'ELBE'], stdout=ELBE_LOGGING)
    CompletedProcess(args=['echo', 'ELBE'], returncode=0)

    Let's redirect the loggers to current stdout

    >>> from elbepack.log import open_logging
    >>> open_logging({"streams":sys.stdout})

    >>> run(['echo', 'ELBE'], stdout=ELBE_LOGGING)
    [CMD] echo ELBE
    ELBE
    ELBE
    CompletedProcess(args=['echo', 'ELBE'], returncode=0)
    """
    stdout = kwargs.pop('stdout', None)
    stderr = kwargs.pop('stderr', None)

    with contextlib.ExitStack() as stack:
        if stdout is ELBE_LOGGING or stderr is ELBE_LOGGING:
            log_fd = stack.enter_context(async_logging_ctx())
            if stdout is ELBE_LOGGING:
                stdout = log_fd
            if stderr is ELBE_LOGGING:
                stderr = log_fd

        logging.info(log_cmd or _log_cmd(cmd), extra={'context': '[CMD] '})
        return subprocess.run(cmd, stdout=stdout, stderr=stderr, check=check, **kwargs)


def do(cmd, /, *, check=True, env_add=None, log_cmd=None, **kwargs):
    """do() - Execute cmd in a shell and redirect outputs to logging.

    Throws a subprocess.CalledProcessError if cmd returns none-zero and check=True

    --

    Let's redirect the loggers to current stdout
    >>> import sys
    >>> from elbepack.log import open_logging
    >>> open_logging({"streams":sys.stdout})

    >>> do("true")
    [CMD] true

    >>> do("false", check=False)
    [CMD] false

    >>> do("cat -", input=b"ELBE")
    [CMD] cat -

    >>> do("cat - && false", input=b"ELBE") # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: ...

    >>> do("false") # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: ...
    """

    new_env = os.environ.copy()
    if env_add:
        new_env.update(env_add)

    logging.info(log_cmd or _log_cmd(cmd), extra={'context': '[CMD] '})

    with async_logging_ctx() as w:
        subprocess.run(cmd, shell=_is_shell_cmd(cmd), stdout=w, stderr=subprocess.STDOUT,
                       env=new_env, check=check, **kwargs)


def chroot(directory, cmd, /, *, env_add=None, **kwargs):
    """chroot() - Wrapper around do().

    --

    Let's redirect the loggers to current stdout

    >>> import sys
    >>> from elbepack.log import open_logging
    >>> open_logging({"streams":sys.stdout})

    >>> chroot("/", "true") # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: ...
    """

    new_env = {'LANG': 'C',
               'LANGUAGE': 'C',
               'LC_ALL': 'C'}
    if env_add:
        new_env.update(env_add)

    if _is_shell_cmd(cmd):
        do(['/usr/sbin/chroot', directory, '/bin/sh', '-c', cmd], env_add=new_env, **kwargs)
    else:
        do(['/usr/sbin/chroot', directory] + cmd, env_add=new_env, **kwargs)


def get_command_out(cmd, /, *, check=True, env_add=None, **kwargs):
    """get_command_out() - Like do() but returns stdout.

    --

    Let's quiet the loggers

    >>> import os
    >>> from elbepack.log import open_logging
    >>> open_logging({"files":os.devnull})

    >>> get_command_out("echo ELBE")
    b'ELBE\\n'

    >>> get_command_out("false") # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: ...

    >>> get_command_out("false", check=False)
    b''

    >>> get_command_out("cat -", input=b"ELBE", env_add={"TRUE":"true"})
    b'ELBE'
    """

    new_env = os.environ.copy()

    if env_add:
        new_env.update(env_add)

    logging.info(_log_cmd(cmd), extra={'context': '[CMD] '})

    with async_logging_ctx() as w:
        ps = subprocess.run(cmd, shell=_is_shell_cmd(cmd), stdout=subprocess.PIPE, stderr=w,
                            env=new_env, check=check, **kwargs)
        return ps.stdout


def env_add(d):
    env = os.environ.copy()
    env.update(d)
    return env
