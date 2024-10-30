## Prerequsites

```
$ ansible-galaxy collection install -r requirements.yml
```

## Running the playbook

Should be as simple as:

```
$ ansible-playbook -l ipaservers site.yml
```

In subsequent runs, certain slow tasks, such as enabling repositories via RHSM,
or ensuring packages are installed, can be skipped by adding `--skip-tags
slow`.

To speed up repeatedly running the playbook, use tags to ensure that only
certain parts of the playbook are processed. For example, `-t chrony` will run
only the chrony related tasks.

## Host Enrolment

Before a host has been joined to the domain, use host variables to specify
connection credentials (`ansible_user` and `ansible_password`) and the host's
OTP (`ipa_client_otp`).

The play will end immediately after the host is joined to the domain. At this
point, remove `ansible_user` and `ansible_password` and re-run the
`ansible-playbook` command.
