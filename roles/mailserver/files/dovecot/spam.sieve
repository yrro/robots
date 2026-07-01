require ["fileinto", "mailbox"];

if header :is "X-Spam" "Yes" {
    fileinto :create "Spam";
    stop;
}

# vim: ts=8 sts=4 sw=4 et
