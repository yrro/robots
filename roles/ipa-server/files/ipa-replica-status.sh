#!/bin/bash

set -eu -o pipefail

domain=$(crudini --get /etc/ipa/default.conf global domain)
ds_instance=$(<<< "${domain//./-}" tr a-z A-Z)

dsconf -j "$ds_instance" replication list \
    | jq '.items[]' -r \
    | xargs -P8 -i -- dsconf -j "$ds_instance" repl-agmt list --suffix={} \
    | jq '.items[].attrs | (.nsds5replicalastupdatestatusjson[0] | fromjson) as $status | [.nsds5replicaroot[0], .cn[0], $status.state, "\((10 * (now - ($status.date | fromdate)) | round) / 10) s", $status.repl_rc_text, $status.ldap_rc_text] | @tsv' -r \
    | sort \
    | column -s$'\t' -t -N SUFFIX,AGREEMENT,STATE,TIME-SINCE,REPL-STATUS,LDAP-STATUS

# vim: ts=8 sts=4 sw=4 et
