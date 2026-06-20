#!/bin/bash

set -eEuo pipefail

class="$1"
user="$2"

case "$class" in
spam|ham)
    ;;
*)
    printf "class=%q user=%q action=NONE" "$class" "$user" | logger -p maill.err -t rspamd-report
    exit 0
esac

printf "class=%q user=%q action=REPORT" "$class" "$user" | logger -p mail.info -t rspamd-report
exec /usr/bin/rspamc -h localhost "learn_${class}"

# vim: ts=8 sts=4 sw=4 et
