#!/bin/bash

set -eEuo pipefail

read -r user

if [[ -z $user ]]; then
    logger -t wrap-dsync-server -p mail.err "no user specified"
    exit 1
fi

command=(doveadm dsync-server -u "$user")
logger -t wrap-dsync-server -p mail.info "exec ${command[*]}"

exec "${command[@]}"

# vim: ts=8 sts=4 sw=4 et
