#!/usr/bin/python3

import collections
import json
import os
from pathlib import Path
import subprocess

from prometheus_client import CollectorRegistry, Enum, write_to_textfile

p = subprocess.run(["ipa-healthcheck", "--output-type=json", "--all"], check=False, stdout=subprocess.PIPE, universal_newlines=True)
results = json.loads(p.stdout)

prom_reg = CollectorRegistry()
states=["SUCCESS", "WARNING", "ERROR", "CRITICAL"]
ipa_healthcheck_state = Enum("ipa_healthcheck_state", "State of an ipa-healthcheck check", labelnames=["source", "check", "key"], registry=prom_reg, states=states)

# Some health checks don't have a unique key; keep track of the worst value
# we've seen so far in this dict.
max_state = collections.defaultdict(int)

for result in results:
    # Some health checks don't set the key label; we always want to set a value
    # so that we don't conflate checks with a key and without in rules,
    # silences, etc.
    key = result["source"], result["check"], result["kw"].get("key", "-")
    max_state[key] = max(max_state[key], states.index(result["result"]))
    ipa_healthcheck_state.labels(*key).state(states[max_state[key]])

output_dir = Path(os.environ["IPA_HEALTHCHECK_PROMETHEUS_OUTPUT_DIR"])
write_to_textfile(output_dir / "ipa-healthcheck-prometheus.prom", prom_reg)

# vim: ts=8 sts=4 sw=4 et
