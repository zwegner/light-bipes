light-bipes
====
`light-bipes` is a very basic TCP tunneling server. The intention of light-bipes is to make a
simple version of ngrok for remote access to large numbers of devices in the form of a Python library,
so that it can be integrated with other management code.

Why not asyncio?
---
Why bother? `asyncio` is pretty complicated, and this library is simple enough to not need it.
`light-bipes` is mostly just a small wrapper around kqueue/epoll.

Why not selectors?
---
I almost converted to `selectors` when adding epoll support. It almost has the API we want, but it's
missing the critical feature of one-shot notifications. This can be worked around, but in a
multi-threading context it would require a lock around the wait()/unregister() combo (so another
thread can't pick up events on the same file descriptor, possibly reordering data in the receiving
stream). The kqueue/epoll specific code is pretty small anyways, so whatever.

What the hell does "light bipes" mean?
----
The day I started writing this, my friend and I were making a dumb joke about mispronouncing "light pipes",
for reasons completely unrelated to software. It was stuck in my head, and when I was thinking of a name for
this project, I realized the name fit pretty well (lightweight pipes between machines). I'm sure I'll regret
this decision before too long.
