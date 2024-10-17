#!/bin/bash

set -eu -o pipefail

DRY_RUN=${DRY_RUN:-1}
DEBUG_RETAIN_DAYS=${DEBUG_RETAIN_DAYS:-60}
RLF_RETAIN_DAYS=${RLF_RETAIN_DAYS:-14}

if [[ $DRY_RUN -ne 0 ]]; then
    echo 'This is a dry-run; no files will be removed'
fi

echo Context: $(id -Z)

for subsystem in acme ca kra pki; do
    dir="/var/log/pki/pki-tomcat/$subsystem"

    # debug logs are rotated daily, so we can simply delete everything except
    # the last N logfiles. According to
    # <https://github.com/dogtagpki/pki/wiki/Configuring-Subsystem-Debug-Log>,
    # these files are purged after 7 days, but even through the files at
    # </usr/share/pki/*/webapps/*/WEB-INF/classes/logging.properties> set
    # "org.apache.juli.FileHandler.maxDays = 7", log rotation is not observed
    # with <idm-pki-*-11.2.1-1.el9.noarch>.
    (find "$dir" -name 'debug.????-??-??.log' -print0 || true) | LC_COLLATE=C sort -z | head -z -n "-$DEBUG_RETAIN_DAYS"

    # com.netscape.cms.logging.RollingLogFile logs are rotated after 30 days or
    # 2000 KiB; so we have to examine modification times to decide which files
    # to delete. There is an 'expirationTime' property for each instance of
    # com.netscape.cms.logging.RollingLogFile in </etc/pki/pki-tomcat/*/CS.cfg>
    # but a comment in RollingLogFile.java says that it is not supported, and
    # there's no CS.cfg file for acma/pki subsystems so this property can't be
    # set for them anyway.
    for logfile in selftests.log system transactions signedAudit/{ca_audit,kra_cert-kra_audit}; do
        path="$dir/$logfile"
        if [[ -f $path ]]; then
            datum=$(stat -c %Y "$path")
            find "$dir" -path "$path.*" -not -newermt "@$((datum - "$RLF_RETAIN_DAYS" * 86400))" -print0
        fi
    done
done \
    | \
while IFS= read -r -d $'\0' file _rest; do
    echo "Removing $file"
    if [[ $DRY_RUN -eq 0 ]]; then
        rm "$file"
    fi
done

# vim: ts=8 sts=4 sw=4 et
