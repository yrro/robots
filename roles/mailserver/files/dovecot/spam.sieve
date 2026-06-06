require ["fileinto", "mailbox"];

# need debug logging here...

# rspamd's threshold for the add_header action is 6
if header :contains "X-Spam-Level" "******" {
    fileinto :create "Spam";
    stop;
}

if header :contains "X-Spam-Flag" "YES" {
    fileinto :create "Spam";
    stop;
}

if header :is "X-Spam" "Yes" {
    fileinto :create "Spam";
    stop;
}


#require ["comparator-i;ascii-numeric", "fileinto", "imap4flags", "mailbox", "relational", "spamtestplus"];
#if spamtest :percent :value "ge" :comparator "i;ascii-numeric" "100" {
	#addflag "Junk";
	#addflag "$Junk";
	#fileinto :create "Spam";
	#stop;
#}

# vim: ts=8 sts=4 sw=4 et
