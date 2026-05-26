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
connection credentials (`ansible_user` and `ansible_password`), or if using
public key authentication, `ansible_user` alone.

The play will end immediately after the host is joined to the domain. At this
point, remove the host variables and re-run the `ansible-playbook` command.

## IPA replica installation

Steps to recover after failure:

```
# ipa-server-install --uninstall

# rm /etc/sssd/sssd.conf.deleted

# etckeeper commit -m 'ipa-server uninstall'
```

As an IPA admin:

```
$ ipa server-del HOST
```

... then re-create the host's DNS records, the host entry and add the host to
the ipaservers hostgroup.

... then add your `ansible_user` to the `remote-access` group & re-run the
playbook with `ansible_user` (and any other necessary variables for access with
a local user) defined.

The playbook will end after running ipa-client-install. At this point you need
to re-run it using your domain account, however the cached service ticket for
its `host` service will still be in your credentials cache (`klist`). The
easiest way to remove it is to log in again.

Don't forget to remove the local user from the `remote-access` group when done.
