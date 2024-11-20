#!/usr/bin/python

import sys
import time

from subprocess import run

def main(argv):
    # The service will be started for every change to the crl directory;
    # sleeping here during the 1st activation should prevent a additioal
    # activation for subsequent changes during the duration of the sleep.
    time.sleep(5)

    run(['systemctl', 'try-restart', 'krb5kdc.service'], check=True)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
