#!/usr/bin/python -I

import logging
import os
from pathlib import Path
import shutil
from subprocess import run
import sys

import dbus
from systemd.journal import JournalHandler


logger = logging.getLogger("md-message")

md_domains_dir = Path("/var/lib/httpd/md/domains")

domains = {
    "imap.robots.org.uk": {
        "privkey_file": Path("/etc/pki/dovecot/private/dovecot.pem"),
        "pubcert_file": Path("/etc/pki/dovecot/certs/dovecot.pem"),
        "systemd_unit": "dovecot.service",
    },
    "smtp.robots.org.uk": {
        "privkey_file": Path("/etc/pki/tls/private/postfix.key"),
        "pubcert_file": Path("/etc/pki/tls/certs/postfix.pem"),
        "systemd_unit": "dovecot.service",
    },
}


def main(argv):
    try:
        event, domain = sys.argv[1:]
    except ValueError:
        logger.error("expected 2 arguments; got %r", argv[1:])
        return 1

    log_msg = "event=%s domain=%s"
    log_args = [event, domain]

    try:
        result = drive(event, domain)
    except Exception as e:
        log_msg += " result=ERROR error=%r"
        log_args.append(str(e))
        logger.exception(log_msg, *log_args)
        return 1
    else:
        log_msg += " result=%s"
        log_args.append(result)
        logger.info(log_msg, *log_args)

    return 0


def drive(event, domain):
    domain_data = domains.get(domain)
    if event == "installed" and domain_data:
        bus = dbus.SystemBus()
        systemd = bus.get_object(
            'org.freedesktop.systemd1',
            '/org/freedesktop/systemd1'
        )
        manager = dbus.Interface(
            systemd,
            'org.freedesktop.systemd1.Manager'
        )
        # 'replace' is the standard mode
        manager.StartUnit(f"md-message-installed2@{domain}.service", 'replace')
        return "OK"
    elif event == "__installed2" and domain_data:
        # shutil.copy preserves file mode
        shutil.copy(md_domains_dir/domain/"privkey.pem", domain_data["privkey_file"])
        shutil.copy(md_domains_dir/domain/"pubcert.pem", domain_data["pubcert_file"])
        run(["/usr/bin/systemctl", "try-reload-or-restart", domain_data["systemd_unit"]], check=True)
        return "OK"

    return "NONE"


def excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


if __name__ == "__main__":
    if not sys.stdin or os.environ.get("MD_MESSAGE_LOGGER") == "journal":
        log_config = {"handlers": [JournalHandler(SYSLOG_IDENTIFIER="md-message")], "format": "%(message)s"}
    else:
        log_config = {}
    logging.basicConfig(level="INFO", **log_config)
    sys.excepthook = excepthook
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
