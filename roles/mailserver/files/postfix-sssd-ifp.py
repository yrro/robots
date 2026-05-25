#!/usr/bin/python -I

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import logging
import os
import socket
import sys

from dbus.mainloop.glib import DBusGMainLoop
import dbus
from gi.repository import GLib
from systemd import daemon


logger = logging.getLogger(__name__)

bus = None

def main():
    DBusGMainLoop(set_as_default=True)

    fds = daemon.listen_fds()
    if len(fds) != 1:
        sys.exit(f"Expected exactly 1 socket, received {len(fds)}")

    global bus
    bus = dbus.SystemBus()
    
    ls = socket.fromfd(fds[0], socket.AF_UNIX, socket.SOCK_STREAM)
    with closing(ls):
        ls.setblocking(False)
        ls.listen()
        GLib.io_add_watch(ls, GLib.IO_IN, cb_accept)

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            loop.quit()


def cb_accept(ls, condition):
    state = {}
    try:
        state["cs"], caddr = ls.accept()
        logger.debug("Accept from %r", caddr)
        state["cs"].setblocking(False)
        GLib.io_add_watch(state["cs"], GLib.IO_IN, cb_read, state)
    except Exception as e:
        logger.exception("Failed to accept connection")
        if "cs" in state:
            close_connection(state)
    return True


def cb_read(cs, condition, state):
    try:
        if condition & (GLib.IO_HUP| GLib.IO_ERR):
            close_connection(state)
            return False

        chunk = cs.recv(4096)
        if not chunk:
            logger.info("EOS")
            close_connection(state)
            return False

        if "buffer" not in state:
            state["buffer"] = b""
        state["buffer"] += chunk

        return not process_buffer(state)
    except:
        logger.exception("Read error")
        close_connection(state)
        return False


def process_buffer(state):
    """
    Scan the buffer.
    If it's incomplete, return False.
    If it's bad, close the connection and return True.
    If it's good, process the request and return True.
    Errors will be handled by cb_read, so we can throw.
    """
    if b":" not in state["buffer"]:
        if len(state["buffer"]) > 3:
            logger.error("Request length too long")
            close_connection(state)
            return True
        else:
            return False

    nbytes_str, remainder = state["buffer"].split(b":", maxsplit=1)
    if not nbytes_str.isdigit():
        logger.error("Request length invalid")
        close_connection(state)
        return True

    nbytes = int(nbytes_str)
    if nbytes > 127:
        logger.error("Request too long")
        close_connection(state)
        return True

    if len(remainder) < nbytes + 1:
        return False

    payload = remainder[:nbytes]
    if remainder[nbytes:nbytes+1] != b",":
        logger.error("Request not terminated")
        close_connection(state)
        return True

    # Process the message
    try:
        req = payload.decode("us-ascii")
        match req.split(maxsplit=1):
            case (mapname, key):
                state["mapname"] = mapname
                state["key"] = key
                dispatch_ifp_request(state)
                return True
            case _:
                logger.error("Malformed request: %r", req)
                respond(state, "PERM", "malformed request")
                close_connection(state)
                return True
    except Exception as e:
        e.add_note(f"state: {state!r}")
        logger.exception("Error processing request")
        respond(state, "TEMP", str(e))
        close_connection(state)
        return True


def close_connection(state):
    logger.debug("goodbye %r", state)
    try:
        state["cs"].close()
    except Exception:
        logger.exception("Closing %r", state["cs"])


def dispatch_ifp_request(state):
    key = state["key"]
    mapname = state["mapname"]

    local_part, _, domain = key.partition("@")
    if domain not in ("", socket.gethostname()):
        logger.info("mapname=%r key=%r NOTFOUND (external domain)", mapname, key)
        respond(state, f"NOTFOUND", "")
        close_connection(state)
        return

    ifp_users = bus.get_object(
        "org.freedesktop.sssd.infopipe", "/org/freedesktop/sssd/infopipe/Users"
    )

    ifp_users.FindByName(
        local_part,
        dbus_interface="org.freedesktop.sssd.infopipe.Users",
        reply_handler=lambda path: handle_reply_find_by_name(state, path),
        error_handler=lambda err: handle_error_find_by_name(state, err),
    )


def handle_reply_find_by_name(state, user_path):
    bus_user_obj = bus.get_object("org.freedesktop.sssd.infopipe", user_path)
    bus_user_obj.Get(
        "org.freedesktop.sssd.infopipe.Users.User",
        "extraAttributes",
        dbus_interface="org.freedesktop.DBus.Properties",
        reply_handler=lambda attrs: handle_reply_get_attributes(state, attrs),
        error_handler=lambda err: handle_dbus_generic_error(state, err),
    )


def handle_error_find_by_name(state, error):
    if error.get_dbus_name() == "sbus.Error.NotFound":
        logger.info(
            "mapname=%r key=%r NOTFOUND (user not known to domain)",
            state["mapname"],
            state["key"],
        )
        respond(state, "NOTFOUND", "")
        close_connection(state)
    else:
        handle_error_generic(state, error)


def handle_error_generic(state, error):
    logger.error("mapname=%r key=%r TEMP %s", state["mapname"], state["key"], error)
    respond(state, "TEMP", str(error))
    close_connection(state)


def handle_reply_get_attributes(state, attrs):
    requested_attrs = attrs.get(state["mapname"], [])

    if not requested_attrs:
        logger.info("mapname=%r key=%r NOTFOUND (missing attribute)", state["mapname"], state["key"])
        respond(state, "NOTFOUND", "")
        close_connection(state)
        return

    value = ", ".join(requested_attrs)
    logger.info("mapname=%r key=%r OK %s", state["mapname"], state["key"], value)
    respond(state, "OK", value)
    close_connection(state)


def respond(state, code, value):
    msg = f"{code} {value}".encode("us-ascii")
    msg_len = str(len(msg)).encode("us-ascii")
    state["cs"].sendall(msg_len + b":" + msg + b",")


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    sys.exit(main())
