#!/usr/bin/python3

from datetime import timezone
from logging import basicConfig, getLogger
import os
from pathlib import Path
import sys

from cryptography import x509
from cryptography.hazmat.primitives import serialization
import ldap3
from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

logger = getLogger("ipa-pki-crl-fetch")

prom_reg = CollectorRegistry()
prom_crl_last_update = Gauge("ipa_pki_crl_last_update_time_seconds", "Timestamp of CRL last update", ("path", "issuer"), registry=prom_reg)
prom_crl_next_update = Gauge("ipa_pki_crl_next_update_time_seconds", "Timestamp of CRL next update", ("path", "issuer"), registry=prom_reg)
prom_crl_number = Gauge("ipa_pki_crl_number", "Monotonically increasing sequence number for a given CRL scope and CRL issuer", ("path", "issuer"), registry=prom_reg)
prom_status = Gauge("ipa_pki_crl_fetch_completion_time_seconds", "Timestamp of successful CRL fetch", registry=prom_reg)

crl_dir = Path(os.environ["IPA_PKI_CRL_FETCH_CRL_DIR"])
crl_file = crl_dir / "ipa-ca.crl"

prom_dir = Path(os.environ["IPA_PKI_CRL_FETCH_PROM_DIR"])
prom_file = prom_dir / "ipa-pki-crl-fetch.prom"


def main(argv):
    basicConfig(level=os.environ.get("IPA_PKI_CRL_FETCH_LOG_LEVEL", "INFO").upper())

    search_args = {
        "search_base": "cn=MasterCRL,ou=crlIssuingPoints,ou=ca,o=ipaca",
        "search_filter": "(objectClass=crlIssuingPointRecord)", 
        "attributes": ["certificateRevocationList"],
    }

    con = ldap3.Connection(ldap3.Server(os.environ["IPA_PKI_CRL_FETCH_LDAP_URL"]), auto_bind=True, authentication="SASL", sasl_mechanism="EXTERNAL", client_strategy=ldap3.ASYNC_STREAM)
    psearch = con.extend.standard.persistent_search(**search_args, streaming=False)
    psearch.start()
    try:
        mid = con.search(**search_args)
        responses, results = con.get_response(mid)
        for entry in responses:
            output(entry)

        while True:
            presponses = psearch.next(block=True)
            for entry in presponses:
                output(entry)
    finally:
        psearch.stop()

    return 0


def output(entry):
    if "certificateRevocationList" not in entry["attributes"]:
        logger.error("certificateRevocationList missing!")
        return
    else:
        new_crl = x509.load_der_x509_crl(entry["attributes"]["certificateRevocationList"][0])

    try:
        old_crl = x509.load_pem_x509_crl(crl_file.read_bytes())
    except:
        logger.exception("Unable to read CRL from %r", crl_file)
        old_crl_number = None
    else:
        old_crl_number = old_crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number

    new_crl_number = new_crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number
    if old_crl_number == new_crl_number:
        logger.info("CRL number %d already fetched", old_crl_number)
        return

    logger.info("Entry %r old CRL number=%r; new CRL number=%r", entry["dn"], old_crl_number, new_crl_number)

    prom_crl_last_update.labels(crl_file, new_crl.issuer.rfc4514_string()).set(new_crl.last_update.replace(tzinfo=timezone.utc).timestamp())
    prom_crl_next_update.labels(crl_file, new_crl.issuer.rfc4514_string()).set(new_crl.next_update.replace(tzinfo=timezone.utc).timestamp())
    prom_crl_number.labels(crl_file, new_crl.issuer.rfc4514_string()).set(new_crl_number)
    prom_status.set_to_current_time()

    crl_file.write_bytes(new_crl.public_bytes(serialization.Encoding.PEM))

    write_to_textfile(prom_file, prom_reg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
