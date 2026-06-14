#!/bin/bash

set -eEuo pipefail

exec kinit -X X509_user_identity=PKCS11:opensc-pkcs11.so "$@"
