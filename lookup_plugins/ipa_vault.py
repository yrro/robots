# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

import ipalib

__metaclass__ = type

DOCUMENTATION = r"""
  name: ipa_vault
  author: Sam Morris <sam@robots.org.uk>
  short_description: reads data from a FreeIPA vault
  description:
  - This lookup returns the contents from a FreeIPA vault.
  - If username, service or shared are specified then the vault from the appropriate namespace will be used.
  options:
    _terms:
      description: name(s) of vaults to read
      required: True
    username:
      description:
      - The vault will be read from the specified user's namespace.
      ini:
      - section: ipa_vault_lookup
        key: username
    service:
      description:
      - The vault will be read from the specified service's namespace.
      ini:
      - section: ipa_vault_lookup
        key: service
    shared:
      type: boolean
      description:
      - The vault will be read from the shared namespace.
      ini:
      - section: ipa_vault_lookup
        key: shared
"""

display = Display()


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        # First of all populate options,
        # this will already take into account env vars and ini config
        self.set_options(var_options=variables, direct=kwargs)

        vault_kwargs = {}
        username = self.get_option("username")
        service = self.get_option("service")
        shared = self.get_option("shared")
        if username and service or username and shared or service and shared:
            raise AnsibleParserError("Only one of username/service/shared may be given")
        elif username:
            vault_kwargs = {"username": str(username)}
        elif service:
            vault_kwargs = {"service": str(service)}
        elif shared:
            vault_kwargs = {"shared": shared}

        ipalib.api.bootstrap(context="client")
        with ipalib.api:
            # lookups in general are expected to both take a list as input and output a list
            # this is done so they work with the looping construct 'with_'.
            ret = []
            for term in terms:
                try:
                    res = ipalib.api.Command.vault_retrieve(term, **vault_kwargs)
                except ipalib.errors.PublicError as e:
                    raise AnsibleError("FreeIPA vault error") from e

                if not res["result"]["data"]:
                    raise AnsibleError(f"FreeIPA vault is empty: {term}")

                ret.append(res["result"]["data"].decode("ascii"))

            return ret
