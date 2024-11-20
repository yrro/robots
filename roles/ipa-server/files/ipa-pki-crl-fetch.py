#!/usr/bin/python3

from pathlib import Path
from subprocess import run
import sys

from cryptography import x509
from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

prom_reg = CollectorRegistry()
prom_crl_last_update = Gauge("ipa_pki_crl_last_update_time_seconds", "Timestamp of CRL last update", ("path", "issuer"), registry=prom_reg)
prom_crl_next_update = Gauge("ipa_pki_crl_next_update_time_seconds", "Timestamp of CRL next update", ("path", "issuer"), registry=prom_reg)
prom_crl_number = Gauge("ipa_pki_crl_number", "Monotonically increasing sequence number for a given CRL scope and CRL issuer", ("path", "issuer"), registry=prom_reg)
prom_status = Gauge("ipa_pki_crl_fetch_completion_time_seconds", "Timestamp of successful CRL fetch", registry=prom_reg)

crl_dir = Path("/var/local/pki/crl")
crl_file_bin = crl_dir / "ipa-ca.crl.bin"
crl_file = crl_dir / "ipa-ca.crl"


def main(argv):
    download_crl()
    convert_crl()
    openssl_rehash()
    record_success()
    return 0


def download_crl():
    run(["curl", "-sS", "-m", "10", "-L", "-o", crl_file_bin, "http://localhost/ipa/crl/MasterCRL.bin"], check=True)


def convert_crl():
    crl_file_tmp = crl_dir / "ipa-ca.crl.tmp"
    run(["openssl", "crl", "-inform", "der", "-in", crl_file_bin, "-out", crl_file_tmp], check=True)
    crl_file_bin.unlink()

    crl_file_tmp.rename(crl_file)
    crl = x509.load_pem_x509_crl(crl_file.read_bytes())
    prom_crl_last_update.labels(crl_file, crl.issuer.rfc4514_string()).set(crl.last_update.timestamp())
    prom_crl_next_update.labels(crl_file, crl.issuer.rfc4514_string()).set(crl.next_update.timestamp())
    prom_crl_number.labels(crl_file, crl.issuer.rfc4514_string()).set(crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number)


def openssl_rehash():
    run(["openssl", "rehash", crl_dir], check=True)


def record_success():
    prom_status.set_to_current_time()
    write_to_textfile("/srv/node-exporter/ipa-pki-crl-fetch.prom", prom_reg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
