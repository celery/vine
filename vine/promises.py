from __future__ import absolute_import, unicode_literals

import sys

from collections import deque

from .abstract import Thenable
from .five import reraise

__all__ = ['promise']


class promise(object):
    """Future evaluation.

    This is a special implementation of promises in that it can
    be used both for "promise of a value" and lazy evaluation.
    The biggest upside for this is that everything in a promise can also be
    a promise, e.g. filters, callbacks and errbacks can all be promises.

    Usage examples:

    .. code-block:: python

        >>> from __future__ import print_statement  # noqa
        >>> p = promise()
        >>> p.then(promise(print, ('OK',)))  # noqa
        >>> p.on_error = promise(print, ('ERROR',))  # noqa
        >>> p(20)
        OK, 20
        >>> p.then(promise(print, ('hello',)))  # noqa
        hello, 20


        >>> p.throw(KeyError('foo'))
        ERROR, KeyError('foo')


        >>> p2 = promise()
        >>> p2.then(print)  # noqa
        >>> p2.cancel()
        >>> p(30)

    Example:

    .. code-block:: python

        from vine import promise, wrap

        class Protocol(object):

            def __init__(self):
                self.buffer = []

            def receive_message(self):
                return self.read_header().then(
                    self.read_body).then(
                        wrap(self.prepare_body))

            def read(self, size, callback=None):
                callback = callback or promise()
                tell_eventloop_to_read(size, callback)
                return callback

            def read_header(self, callback=None):
                return self.read(4, callback)

            def read_body(self, header, callback=None):
                body_size, = unpack('>L', header)
                return self.read(body_size, callback)

            def prepare_body(self, value):
                self.buffer.append(value)

    """
    if not hasattr(sys, 'pypy_version_info'):  # pragma: no cover
        __slots__ = (
            'fun', 'args', 'kwargs', 'ready', 'failed',
            'value', 'reason', '_svpending', '_lvpending',
            'on_error', 'cancelled',
        )

    def __init__(self, fun=None, args=None, kwargs=None,
                 callback=None, on_error=None):
        self.fun = fun
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.ready = False
        self.failed = False
        self.value = None
        self.reason = None
        self._svpending = None
        self._lvpending = None
        self.on_error = on_error
        self.cancelled = False

        if callback is not None:
            self.then(callback)

        if self.fun:
            assert callable(fun)

    def __repr__(self):
        if self.fun:
            return '<promise@0x{0:x}: {1!r}>'.format(id(self), self.fun)
        return '<promise@0x{0:x}>'.format(id(self))

    def cancel(self):
        self.cancelled = True
        try:
            if self._svpending is not None:
                self._svpending.cancel()
            if self._lvpending is not None:
                for pending in self._lvpending:
                    pending.cancel()
            if isinstance(self.on_error, Thenable):
                self.on_error.cancel()
        finally:
            self._svpending = self._lvpending = self.on_error = None

    def __call__(self, *args, **kwargs):
        retval = None
        if self.cancelled:
            return
        final_args = self.args + args if args else self.args
        final_kwargs = dict(self.kwargs, **kwargs) if kwargs else self.kwargs
        if self.fun:
            try:
                retval = self.fun(*final_args, **final_kwargs)
                self.value = (ca, ck) = (retval,), {}
            except Exception:
                return self.throw()
        else:
            self.value = (ca, ck) = final_args, final_kwargs
        self.ready = True
        svpending = self._svpending
        if svpending is not None:
            try:
                svpending(*ca, **ck)
            finally:
                self._svpending = None
        else:
            lvpending = self._lvpending
            try:
                while lvpending:
                    p = lvpending.popleft()
                    p(*ca, **ck)
            finally:
                self._lvpending = None
        return retval

    def then(self, callback, on_error=None):
        if not isinstance(callback, Thenable):
            callback = promise(callback, on_error=on_error)
        if self.cancelled:
            callback.cancel()
            return callback
        if self.failed:
            callback.throw(self.reason)
        elif self.ready:
            args, kwargs = self.value
            callback(*args, **kwargs)
        if self._lvpending is None:
            svpending = self._svpending
            if svpending is not None:
                self._svpending, self._lvpending = None, deque([svpending])
            else:
                self._svpending = callback
                return callback
        self._lvpending.append(callback)
        return callback

    def throw1(self, exc):
        if self.cancelled:
            return
        self.failed, self.reason = True, exc
        if self.on_error:
            self.on_error(exc)

    def throw(self, exc=None, tb=None):
        if self.cancelled:
            return
        _exc = sys.exc_info()[1] if exc is None else exc
        try:
            self.throw1(_exc)
            svpending = self._svpending
            if svpending is not None:
                try:
                    svpending.throw1(_exc)
                finally:
                    self._svpending = None
            else:
                lvpending = self._lvpending
                try:
                    while lvpending:
                        lvpending.popleft().throw1(_exc)
                finally:
                    self._lvpending = None
        finally:
            if self.on_error is None:
                if exc is None:
                    raise
                reraise(type(exc), exc, tb)

    @property
    def listeners(self):
        if self._lvpending:
            return self._lvpending
        return [self._svpending]

Thenable.register(promise)
