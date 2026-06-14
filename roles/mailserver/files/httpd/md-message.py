#!/usr/bin/python -I

import logging
import os
from pathlib import Path
import selinux
import shutil
import subprocess
import sys
import time

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
        "privkey_file": Path("/etc/pki/tls/private/postfix-msa.key"),
        "pubcert_file": Path("/etc/pki/tls/certs/postfix-msa.pem"),
        "systemd_unit": "postfix.service",
    },
    "mail-in.robots.org.uk": {
        "privkey_file": Path("/etc/pki/tls/private/postfix.key"),
        "pubcert_file": Path("/etc/pki/tls/certs/postfix.pem"),
        "postfix_tls": True,
    },
}


def main(argv):
    try:
        event, domain = sys.argv[1:]
    except ValueError:
        logger.error("expected 2 arguments; got %r", argv[1:])
        return 1

    log_msg = "event=%s euid=%s context=%s domain=%s"
    log_args = [event, os.geteuid(), selinux.getcon()[1], domain]

    try:
        action = drive(event, domain)
    except Exception as e:
        log_msg += " action=ERROR error=%r"
        log_args.append(str(e))
        logger.exception(log_msg, *log_args)
        return 1
    else:
        log_msg += " action=%s"
        log_args.append(action)
        logger.info(log_msg, *log_args)

    return 0


def drive(event, domain):
    domain_data = domains.get(domain)
    man = get_systemd_manager()

    match event:
        case "renewed":
            # We have been invoked by httpd (running as apache).
            # A certificate is staged. Schedule an httpd restart.
            if domain_data:
                man.StartUnit("md-message-renewed2.service", "replace")
                return "RELOAD_SCHEDULED"
        case "_renewed2":
            # We have been invoked within md-message-renewed2.service.
            # Wait before reload httpd, in case mod_md is busy driving other certificates.
            time.sleep(15)
            man.ReloadOrTryRestartUnit("httpd.service", "replace")
            return "RELOAD_TRIGGERED"
        case "installed":
            # We have been invoked by httpd. We can't directly install
            # certificates because we're confined by httpd_t.
            if domain_data:
                domain_escaped = systemd_escape(domain)
                man.StartUnit(
                    f"md-message-installed2@{domain_escaped}.service", "replace"
                )
                return "INSTALL_TRIGGERED"
        case "_installed2":
            if domain_data:
                new_privkey_file = md_domains_dir / domain / "privkey.pem"
                new_pubkey_file = md_domains_dir / domain / "pubcert.pem"
                # shutil.copy preserves file mode
                shutil.copy(new_privkey_file, domain_data["privkey_file"])
                shutil.copy(new_pubkey_file, domain_data["pubcert_file"])
                if systemd_unit := domain_data.get("systemd_unit"):
                    man.ReloadOrTryRestartUnit(systemd_unit, "replace")
                if domain_data.get("postfix_tls"):
                    p = subprocess.run(
                        [
                            "postfix",
                            "tls",
                            "deploy-server-cert",
                            domain_data["pubcert_file"],
                            domain_data["privkey_file"],
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    if p.returncode != 0:
                        raise RuntimeError(p.stderr)
                return "INSTALLED"
        case event_name if event_name.startswith("_"):
            raise ValueError(f"Invalid event {event_name!r}")

    return "NONE"


def get_systemd_manager():
    bus = dbus.SystemBus()
    systemd = bus.get_object("org.freedesktop.systemd1", "/org/freedesktop/systemd1")
    manager = dbus.Interface(systemd, "org.freedesktop.systemd1.Manager")
    return manager


def systemd_escape(s):
    p = subprocess.run(
        ["systemd-escape", s], text=True, capture_output=True, check=False
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    return p.stdout.rstrip()


def excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


if __name__ == "__main__":
    if not sys.stdin or os.environ.get("MD_MESSAGE_LOGGER") == "journal":
        log_config = {
            "handlers": [JournalHandler(SYSLOG_IDENTIFIER="md-message")],
            "format": "%(message)s",
        }
    else:
        log_config = {}
    logging.basicConfig(level="INFO", **log_config)
    sys.excepthook = excepthook
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
