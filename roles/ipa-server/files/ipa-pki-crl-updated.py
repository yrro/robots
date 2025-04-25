#!/usr/bin/python3

import sys
import time

from subprocess import run

def main(argv):
    # The service will be started for every change to the crl directory;
    # sleeping here during the 1st activation should prevent additioal
    # activations for subsequent changes during the duration of the sleep.
    time.sleep(5)

    # Docs say that all files in the directory will be read, so rehash failure
    # is not fatal.
    run(["openssl", "rehash", "/var/kerberos/krb5kdc/crl"], check=False)

    run(['systemctl', 'try-restart', 'krb5kdc.service'], check=True)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
