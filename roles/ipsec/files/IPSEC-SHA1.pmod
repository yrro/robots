# SHA1 has been disabled since RHEL 8. However this was not enforced upon
# libreswan's 'authby' connection parameter until RHEL 9, resulting in the
# following error when trying to connect to EdgeOS:
#
# "authentication failed: peer authentication requires policy RSASIG_v1_5"
#
# This policy re-enables the use of RSA1, but only for IKE. Alternatively,
# 'rsa-sha1' can be added to a connection's 'authby' parameter.

sign@ike = RSA-SHA1+

# vim: ft=cfg ts=8 sts=4 sw=4 et
