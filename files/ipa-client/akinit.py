#!/usr/bin/python -I

from subprocess import run
import sys
import tempfile

def main():
    with tempfile.NamedTemporaryFile(prefix="akinit-ccache-") as ccache:
        for _ in range(5):
            ps = run(["klist", "-s", "-c", ccache.name])
            if ps.returncode != 0:
                print("Acquiring TGT for secure authentication tunnel...")
                pf = run(["kinit", "-V", "-n", "-c", ccache.name])
                if pf.returncode != 0:
                    print("Failed to aquire FAST TGT!")
                    return 1
                print("Acquiring TGT...")

            pt = run(["kinit", "-V", "-T", ccache.name])
            if pt.returncode == 0:
                return 0

if __name__ == "__main__":
    sys.exit(main())

# vim: ts=8 sts=4 sw=4 et
