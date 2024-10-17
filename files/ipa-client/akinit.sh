#!/bin/bash

set -eu -o pipefail

armor_cc=$(mktemp --tmpdir="${XDG_RUNTIME_DIR}" krbcc_anon.XXXXXXXXXX)
trap "rm -f ${armor_cc}" EXIT

if ! kinit -V -n -l 5m -a -F -P -c "$armor_cc"; then
    echo "Unable to obtain ticket for anonymous principal" >&2
    exit 1
fi

kinit -T "$armor_cc" "$@"

# vim: ts=8 sts=4 sw=4 et
