#!/usr/bin/python3

from datetime import datetime, timedelta, timezone
from logging import basicConfig, getLogger
import os
from pathlib import Path
import random
import ssl
import sys
import signal
import threading

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

prom_dir = os.environ["IPA_PKI_CRL_FETCH_PROM_DIR"]
prom_file = Path(prom_dir) / "ipa-pki-crl-fetch.prom" if prom_dir else None


def main(argv):
    basicConfig(level=os.environ.get("IPA_PKI_CRL_FETCH_LOG_LEVEL", "INFO").upper())
    ldap3.utils.log.set_library_log_detail_level(int(os.environ.get("IPA_PKI_CRL_FETCH_LDAP_LOG_LEVEL", "0")))

    exit_ = threading.Event()

    def handle_signal(signum, frame):
        logger.debug("Caught %r", signal.Signals(signum).name)
        exit_.set()
    signal.signal(signal.SIGTERM, handle_signal)

    server = ldap3.Server(os.environ["IPA_PKI_CRL_FETCH_LDAP_URL"], connect_timeout=6, tls=ldap3.Tls(validate=ssl.CERT_REQUIRED))

    conn = None
    sleep_for = timedelta(0)
    while not exit_.is_set():
        if prom_dir:
            update_metrics()

        logger.info("Next CRL update check in %r", sleep_for)
        exit_.wait(sleep_for.total_seconds())

        try:
            if not conn:
                logger.debug("Connecting to %r", server)
                conn = ldap3.Connection(server, auto_bind=True, authentication="SASL", sasl_mechanism="EXTERNAL", client_strategy="SYNC", read_only=True)
                crl_issuing_point_record = ldap3.ObjectDef(["crlIssuingPointRecord"], conn)
            crl_reader = ldap3.Reader(conn, crl_issuing_point_record, base="ou=crlIssuingPoints,ou=ca,o=ipaca", sub_tree=False, attributes=["certificateRevocationList", "cn", "crlNumber", "thisUpdate", "nextUpdate"])
            crls = crl_reader.search()
        except ldap3.core.exceptions.LDAPException:
            logger.exception("LDAP error")
            conn = None
            sleep_for = timedelta(seconds=45)
            continue

        now = datetime.now(timezone.utc)
        earliest_next_update_in = timedelta.max
        for crl in crls:
            try:
                process_crl(crl)
            except Exception as e:
                logger.exception("While processing CRL %r", crl.cn.value)
                earliest_next_update_in = timedelta.min
            else:
                crl_next_update = datetime.strptime(crl.nextUpdate.value, "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
                logger.debug("CRL %r next update at %s", crl.cn.value, crl_next_update)
                earliest_next_update_in = min(earliest_next_update_in, crl_next_update - now)

        sleep_for = max(timedelta(minutes=1, seconds=random.randint(-15, 14)), earliest_next_update_in/2)

    return 0


def process_crl(crl):
    crl_file = (crl_dir / crl.cn.value).with_suffix(".crl")
    if not crl_file.is_relative_to(crl_dir):
        raise ValueError("Invalid CRL path", crl_file)

    try:
        old_crl = x509.load_pem_x509_crl(crl_file.read_bytes())
    except:
        logger.exception("Unable to read CRL from %r", crl_file)
        old_crl_number = None
    else:
        old_crl_number = old_crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number

    new_crl = x509.load_der_x509_crl(crl.certificateRevocationList.value)
    new_crl_number = new_crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number

    if old_crl_number != new_crl_number:
        logger.info("CRL %r updated %r → %r", crl.cn.value, old_crl_number, new_crl_number)
        crl_file.write_bytes(new_crl.public_bytes(serialization.Encoding.PEM))
    else:
        logger.info("CRL %r %d has no updates", crl.cn.value, old_crl_number)


def update_metrics():
    for crl_file in crl_dir.glob("*.crl"):
        try:
            crl = x509.load_pem_x509_crl(crl_file.read_bytes())
        except:
            logger.exception("Unable to read CRL from %r", crl_file)
            continue

        labelvalues = crl_file, crl.issuer.rfc4514_string()
        prom_crl_last_update.labels(*labelvalues).set(crl.last_update.replace(tzinfo=timezone.utc).timestamp())
        prom_crl_next_update.labels(*labelvalues).set(crl.next_update.replace(tzinfo=timezone.utc).timestamp())
        prom_crl_number.labels(*labelvalues).set(crl.extensions.get_extension_for_oid(x509.CRLNumber.oid).value.crl_number)

    prom_status.set_to_current_time()
    write_to_textfile(prom_file, prom_reg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
