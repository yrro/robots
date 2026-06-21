#!/bin/bash

set -eEuo pipefail

# This wrapper script is launched with AT_SECURE due to the domain transition
# from dovecot_t → dovecot_auth_t.

# Audit the original environment
#(echo "Launching with environment:"; /usr/bin/printenv) | /usr/bin/logger -t wrap-auth

# Sanitize the environment. ld-linux has already removed LD_PRELOAD and
# friends.
export PATH=/usr/local/bin:/usr/bin

exec /usr/libexec/dovecot/auth "$@"
