#!/usr/bin/python

import argparse
import getpass
import secrets
import sys

from ansible.config.manager import ConfigManager
from ansible.module_utils.parsing.convert_bool import boolean
from ipalib import api
import ipalib.errors


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    config = ConfigManager()
    vault_args = {}
    if config._config_file:
        vault_args["username"] = config._get_ini_config_value(
            config._config_file,
            section="ipa-vault",
            option="username",
        )
        vault_args["service"] = config._get_ini_config_value(
            config._config_file,
            section="ipa-vault",
            option="service",
        )
        vault_args["shared"] = config._get_ini_config_value(
            config._config_file,
            section="ipa-vault",
            option="shared",
        )
        if vault_args["shared"]:
            vault_args["shared"] = boolean(vault_args["shared"])

    api.bootstrap(context="client")
    api.finalize()

    api.Backend.rpcclient.connect()
    try:
        if args.archive:
            rc = archive(args, vault_args)
        else:
            rc = retrieve(args, vault_args)
    finally:
        api.Backend.rpcclient.disconnect()

    return rc


def build_parser():
    parser = argparse.ArgumentParser(
        description="Get a vault password from a FreeIPA vault"
    )
    parser.add_argument(
        "--vault-id",
        action="store",
        default=None,
        dest="vault_id",
        help="name of the vault secret to get from FreeIPA vault",
        required=True,
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        default=None,
        dest="archive",
        help="archive the secret into the vault, instead of retrieving it from the fault",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        default=None,
        dest="random",
        help="generate a random secret instead of prompting",
    )
    return parser


def archive(args, vault_args):
    if args.random:
        data = secrets.token_urlsafe()
    else:
        data = getpass.getpass(f"Password to store in vault {args.vault_id!r}: ")
        if not data:
            print(f"refusing to store an empty password in vault {args.vault_id!r}")
            return 1
    try:
        result = api.Command.vault_archive(
            args.vault_id, data=data.encode("ascii"), **vault_args
        )
    except ipalib.errors.PublicError as e:
        print(e.message, file=sys.stderr)
        return 1

    print(result["summary"])
    return 0


def retrieve(args, vault_args):
    try:
        result = api.Command.vault_retrieve(args.vault_id, **vault_args)
    except ipalib.errors.PublicError as e:
        print(e.message, file=sys.stderr)
        return 1

    if not result["result"]["data"]:
        print(
            f"vault {args.vault_id!r} was empty; refusing to proceed", file=sys.stderr
        )
        return 1

    print(result["result"]["data"].decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
