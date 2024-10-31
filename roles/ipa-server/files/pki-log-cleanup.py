#!/usr/bin/python3

from datetime import date, datetime, timedelta
from itertools import chain
import os
from pathlib import Path
import sys

from logging import basicConfig, getLogger


logger = getLogger("pki-log-cleanup")


def main():
    basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(message)s")

    dry_run = int(os.environ.get("DRY_RUN", "1"))
    if dry_run:
        logger.info("This is a dry-run; no log files will be removed")

    for path in get_paths("pki-tomcat"):
        logger.info("%s %s", "Deleting" if not dry_run else "Not deleting", path)
        if not dry_run:
            path.unlink()


def get_paths(instance):
    for subsystem in ["acme", "ca", "kra", "pki"]:
        log_dir = get_instance_subsystem_log_path(instance, subsystem)
        datum = date.today()
        yield from get_rlf_paths(log_dir, datum)
        yield from get_debug_paths(log_dir, datum)


def get_instance_subsystem_log_path(instance, subsystem):
    assert len(instance) > 0
    assert len(subsystem) > 0
    return Path("/var/log/pki") / instance / subsystem


def get_rlf_paths(log_dir, datum):
    '''
    com.netscape.cms.logging.RollingLogFile logs are rotated after 30 days or
    2000 KiB. There is an 'expirationTime' property for each instance of
    com.netscape.cms.logging.RollingLogFile in </etc/pki/pki-tomcat/*/CS.cfg>
    but a comment in RollingLogFile.java says that it is not supported, and
    there's no CS.cfg file for acma/pki subsystems so this property can't be
    set for them anyway.
    '''
    rlf_retention = int(os.environ.get("RLF_RETAIN_DAYS", "90"))
    assert rlf_retention > 0
    cutoff = datum - timedelta(days=rlf_retention)

    # TODO: remove expiration of 'system' and 'transactions' logs, which were
    # removed in v11.2.0-beta3-656-g043515bd9d
    for glob in ["selftests.log.??????????????", "signedAudit/*.??????????????", "system.??????????????", "transactions.??????????????"]:
        for path in log_dir.glob(glob):
            path_date = datetime.strptime(path.name[-14:-6], "%Y%m%d")
            if path_date.date() < cutoff:
                yield path


def get_debug_paths(log_dir, datum):
    '''
    debug logs are rotated daily. According to
    <https://github.com/dogtagpki/pki/wiki/Configuring-Subsystem-Debug-Log>
    they are purged after 7 days, and even though maxDays is set to 7 in
    </usr/share/pki/*/webapps/*/WEB-INF/classes/logging.properties>, they
    aren't being purged on RHEL 8 or 9.
    '''
    debug_retention = int(os.environ.get("DEBUG_RETAIN_DAYS", "21"))
    assert debug_retention > 0
    cutoff = datum - timedelta(days=debug_retention)

    for path in log_dir.glob("debug.????-??-??.log"):
        path_date = datetime.strptime(path.name[6:16], "%Y-%m-%d")
        if path_date.date() < cutoff:
            yield path


if __name__ == "__main__":
    sys.exit(main())

# vim: ts=8 sts=4 sw=4 et
