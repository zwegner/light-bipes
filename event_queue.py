import select

# Dumb enum for event types
READ, WRITE, ERROR = range(3)

# kqueue interface for BSD
if hasattr(select, 'kqueue'):
    READ_FLAGS = select.KQ_FILTER_READ

    class EventQueue:
        def __init__(self):
            self.kqueue = select.kqueue()

        def _get_register_event(self, fd, oneshot=False):
            action = select.KQ_EV_ADD
            if oneshot:
                action |= select.KQ_EV_ONESHOT
            return select.kevent(fd, READ_FLAGS, action)

        def register(self, fd, oneshot=False):
            self.kqueue.control([self._get_register_event(fd, oneshot=oneshot)], 0)

        def unregister(self, fd):
            event = select.kevent(fd, READ_FLAGS, select.KQ_EV_DELETE)
            self.kqueue.control([event], 0)

        def wait(self, register_fd=None, oneshot=False):
            reg_events = None
            if register_fd:
                reg_events = [self._get_register_event(register_fd, oneshot=oneshot)]
            events = self.kqueue.control(reg_events, 1)
            if not events:
                return None
            assert len(events) == 1
            event = events[0]

            #if event.flags & (select.KQ_EV_ERROR | select.KQ_EV_EOF):
            if event.flags & select.KQ_EV_ERROR:
                event_type = ERROR
            # No write for now, we don't listen for writeability now
            else:
                event_type = READ

            return event.ident, event_type

# epoll interface for linux
elif hasattr(select, 'epoll'):
    class EventQueue:
        def __init__(self):
            self.epoll = select.epoll()

        def register(self, fd):
            self.epoll.register(fd, select.EPOLLIN)

        def unregister(self, fd):
            self.epoll.unregister(fd, select.EPOLLIN)

        def wait(self):
            events = self.epoll.poll(maxevents=1)
            if not events:
                return None
            assert len(events) == 1
            fd, event = events[0]

            if event & select.EPOLLIN:
                event_type = READ
            # No write for now, we don't listen for writeability now
            else:
                event_type = ERROR

            return event.ident, event_type

else:
    assert False, 'need kqueue or epoll support for event queue'
