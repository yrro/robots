## Prerequsites

```
$ ansible-galaxy collection install -r requirements.yml
```

## Running the playbook

Should be as simple as:

```
$ ansible-playbook -b -l ipaservers site.yml
```

In subsequent runs, certain slow tasks, such as enabling repositories via RHSM,
or ensuring packages are installed, can be skipped by adding `--skip-tags
slow`.

To speed up repeatedly running the playbook, use tags to ensure that only
certain parts of the playbook are processed. For example, `-t chrony` will run
only the chrony related tasks.

## Host Enrolment

Before a host has been joined to the domain, specify credentials via command
line options.

For example:

```
$ ipa host-add host.example.com --random
-----------------------------------
Added host "host.example.com"
-----------------------------------
  Host name: host.example.com
  Random password: 2secret2beTru
  Password: True
  Keytab: False
  Managed by: host.example.com
```

Assuming that `root`'s password is available via the `SSHPASS` environment
variable:

```
$ ansible-playbook site.yml -l host.example.com -u root -e ansible_password='{{ lookup("env", "SSHPASS" }}'
```

The playbook will prompt for the host's One Time Password as needed. The play
will end immediately after the host is joined to the domain, so that you can
re-run the playbook without specifying authentication options.
