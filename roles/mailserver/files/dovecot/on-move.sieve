require ["vnd.dovecot.debug", "vnd.dovecot.pipe", "copy", "environment", "vnd.dovecot.imapsieve", "imapsieve", "variables"];

if environment :matches "imap.user" "*" {
  set "user" "${1}";
}

# What about Spam -> Trash -> Inbox? Can we figure out if we should report as
# ham on the 2nd move?
if environment :is "vnd.dovecot.mailbox-from" ["Spam"] {
  if environment :is "vnd.dovecot.mailbox-to" ["Spam", "Trash"] {
    stop;
  }

  debug_log "on-move spam -> elsewhere";
  pipe :copy "rspamd-report" [ "ham", "${user}"];

} elsif environment :is "vnd.dovecot.mailbox-to" ["Spam"] {
  if environment :is "vnd.dovecot.mailbox-from" ["Spam"] {
    stop;
  }

  debug_log "on-move elsewhere -> spam";
  pipe :copy "rspamd-report" [ "spam", "${user}"];

} else {
  debug_log "on-move is confused!";
  stop;
}

# vim: ts=8 sts=2 sw=2 et
