#!/bin/bash

set -eEuo pipefail

class="$1"
user="$2"

case "$class" in
spam|ham)
    ;;
*)
    printf "NOT reporting class=%q user=%q" "$class" "$user" | logger -p maill.err -t rspamd-report
    exit 0
esac

printf "reporting class=%q user=%q" "$class" "$user" | logger -p mail.info -t rspamd-report
# connects to controller (port 11334)
#exec /usr/bin/rspamc -h -P secret "learn_${class}"
exit 0

# vim: ts=8 sts=4 sw=4 et
