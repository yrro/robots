#!/bin/bash

set -eEu -o pipefail

IMAP_PASSWORD=$(<"$CREDENTIALS_DIRECTORY/dmarc-report-viewer.imap-password")
export IMAP_PASSWORD

HTTP_SERVER_PASSWORD=$(<"$CREDENTIALS_DIRECTORY/dmarc-report-viewer.http-server-password")
export HTTP_SERVER_PASSWORD

exec /usr/local/libexec/dmarc-report-viewer
