# Mail relay for internal servers

The mail submission service allows MTAs to authenticate with GSSAPI.

The authenticating Kerberos principal name must have a primary of `smtp`.
The principal's instance will be used to determine valid envelope senders.
For instance, `smtp/foo.realm@REALM` will be allowed to submit mail from `*@foo.realm`.

## Postfix setup

The keytab must be saved at `/var/kerberos/krb5/user/$(id -u postfix)/client.keytab`.
This is because SELinux sets `AT_SECURE` on Postfix's smtp client process, which prevents the `GSS_USE_PROXY=`, `KRB5_CLIENT_KTNAME=`, etc. environment variables from being used.

As such, the keytab must only be readable by the `postfix` user.
SELinux policy will prevent the keytab from being read unless `postfix_smtp_t` is made into a permissive domain, or an SELinux policy module is written allowing:

```
allow postfix_smtp_t krb5_keytab_t:dir search;
allow postfix_smtp_t krb5_keytab_t:file { lock open read };
```

Postfix should be configured with:

```
relayhost = [smtp.robots.org.uk]:465
smtp_tls_wrappermode = yes
smtp_tls_security_level = secure
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = inline:{ smtp.robots.org.uk=-:- }
smtp_sasl_mechanism_filter = gssapi
```
