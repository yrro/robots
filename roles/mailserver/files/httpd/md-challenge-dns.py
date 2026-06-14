#!/usr/bin/python -I

# DNS updates are possible because of this update policy in the zone:
#
#   grant EXAMPLE.COM krb5-subdomain acme-challenge.example.com. TXT;
#
# ... which means "any principal in EXAMPLE.COM with a primary of 'host' may
# update resource records beneath beneath acme-challenge.example.com if the
# type is TXT"; oops!
#
# The best we can do is:
#
#   grant EXAMPLE.COM krb5-selfsub . TXT;
#
# ... which means "any principal in EXAMPLE.COM with a primary of 'host' may
# update resource records beneath its own name if the type is TXT".
#
# Sadly there's no way to combine the behaviour so that we can
# grant the ability to update TXT records beneath a particular domain name to a
# particular principal. :(
#
# Then a special host principal for the mailserver host was created with:
#
#   # ipa host-add --force mailserver.acme-challenge.example.com
#
# To allow the mailserver host to manage the special host's Kerberos keys
# (i.e., obtain a keytab for it), the mailserver is added as a manager of the
# special host:
#
#   # ipa host-add-managedby mailserver.acme-challenge.example.com --hosts=mailserver.example.com
#
# GSS-TSIG code adapted from
# <https://stackoverflow.com/questions/55900836/generate-tsig-keyring-as-encoded-byte-string-for-dns-update>

import logging
import os
import socket
import sys
import time
import uuid

import dns.resolver
import dns.tsig
import dns.update
import gssapi
from systemd.journal import JournalHandler


logger = logging.getLogger("md-challenge-dns")


def main(argv):
    os.environ["GSS_USE_PROXY"] = "1"
    os.environ["GSSPROXY_SOCKET"] = "/var/lib/gssproxy/md-challenge.sock"

    try:
        command, domain, token = argv[1:]
    except ValueError:
        logger.error("expected 3 arguments; got %r", argv[1:])
        return 1

    target_zone, target_relative = resolve_target(dns.name.from_text(domain))
    target_zone_soa = dns.resolver.resolve(target_zone, dns.rdatatype.SOA)
    target_zone_mname = target_zone_soa.rrset[0].mname

    update = dns.update.UpdateMessage(target_zone)
    match command:
        case "setup":
            update.add(target_relative, 10, dns.rdatatype.TXT, token)
        case "teardown":
            update.delete(target_relative, dns.rdatatype.TXT, token)
        case _:
            logger.error("Unknown command %r", command)
            return 1

    target_server = dns.resolver.resolve_name(target_zone_mname)
    success = False
    excs = []
    for addr in target_server.addresses():
        log_msg = "operation=%s opcode=%s rr=%s zone=%s master=%s address=%s"
        log_args = [command, dns.opcode.to_text(update.opcode()), target_relative, target_zone, target_zone_mname, addr]
        try:
            key_name, key_ring = gss_tsig_negotiate(target_zone_mname, addr, None)
            update.use_tsig(keyring=key_ring, keyname=key_name, algorithm=dns.tsig.GSS_TSIG)
            response = dns.query.tcp(update, addr, timeout=5)
            log_msg += " rcode=%s"
            log_args.append(dns.rcode.to_text(response.rcode()))
            if response.rcode() == dns.rcode.NOERROR:
                excs.clear()
                success = True
                break
        except Exception as e:
            log_msg += " error=%r"
            log_args.append(str(e))
            excs.append(e)
            continue
        finally:
            logger.info(log_msg, *log_args)

    if excs:
        raise ExceptionGroup("All DNS update operations failed", excs)

    if not success:
        return 1

    if command == "setup":
        # XXX poll all nameservers until the record is available?
        time.sleep(5)

    return 0


def resolve_target(name):
    challenge_name = dns.name.from_text(f"_acme-challenge", origin=None) + name
    challenge_name_canonical = dns.resolver.canonical_name(challenge_name)
    target_zone = dns.resolver.zone_for_name(challenge_name_canonical)
    target_relative = challenge_name_canonical.relativize(target_zone)
    return target_zone, target_relative


def gss_tsig_negotiate(server_name, server_addr, creds=None):
    # Acquire GSSAPI credentials
    gss_name = gssapi.Name(f"DNS@{server_name}", gssapi.NameType.hostbased_service)
    gss_ctx = gssapi.SecurityContext(name=gss_name, creds=creds, usage="initiate")

    # RFC 2930 suggests key names use the server name in their most significant
    # part
    keyname = dns.name.from_text(f"{uuid.uuid4()}.{server_name}")
    key = dns.tsig.Key(keyname, gss_ctx, dns.tsig.GSS_TSIG)
    keyring = dns.tsig.GSSTSigAdapter({keyname: key})

    token = gss_ctx.step()
    while not gss_ctx.complete:
        tkey_query = build_tkey_query(token, keyring, keyname)
        response = dns.query.tcp(tkey_query, server_addr, timeout=5)
        # Original comment
        # <https://github.com/rthalley/dnspython/pull/530#issuecomment-658959755>:
        # "this if statement is a bit redundant, but if the final token comes
        # back with TSIG attached then the patch to message.py will
        # automatically step the security context. We dont want to excessively
        # step the context."
        if not gss_ctx.complete:
            token = gss_ctx.step(response.answer[0][0].key)

    return keyname, keyring


def build_tkey_query(token, keyring, keyname):
    from dns.rdtypes.ANY.TKEY import TKEY
    datum = int(time.time())
    tkey = TKEY(rdclass=dns.rdataclass.ANY, rdtype=dns.rdatatype.TKEY, algorithm=dns.tsig.GSS_TSIG, inception=datum, expiration=datum, mode=TKEY.GSSAPI_NEGOTIATION, error=dns.rcode.NOERROR, key=token)
    query = dns.message.make_query(keyname, dns.rdatatype.TKEY, dns.rdataclass.ANY)
    query.keyring = keyring
    query.find_rrset(dns.message.ADDITIONAL, keyname, dns.rdataclass.ANY, dns.rdatatype.TKEY, create=True).add(tkey)
    return query


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


if __name__ == "__main__":
    if sys.stdin:
        log_config = {}
    else:
        log_config = {"handlers": [JournalHandler(SYSLOG_IDENTIFIER="md-challenge-dns")], "format": "%(message)s"}
    logging.basicConfig(level="INFO", **log_config)
    sys.excepthook = handle_exception
    sys.exit(main(sys.argv))

# vim: ts=8 sts=4 sw=4 et
