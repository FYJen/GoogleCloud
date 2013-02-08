#!/usr/bin/perl

use Data::Dumper;
use strict;
use warnings;


my $iName_table = $ARGV[0];
my %instanceNames = %$iName_table;
print "instance set .... \n\n";

my $instancePrefix = $ARGV[1];
print "prefex set .... \n\n";

my $IP_table = $ARGV[2]; 
my %IPAddresses = %$IP_table;
print "IPtable set ... \n\n";

# get current host name 
my $myHostName = `hostname`;
chomp($myHostName);
my $myHostNameFull = `hostname -f `;
chomp($myHostNameFull);

# additions to be added to /etc/hosts
my $additions = "";

while (my ($k,$v) = each %instanceNames){
	print "In while loop ... \n\n";
	if (($k =~ /^$instancePrefix/) && ($k ne $myHostName)) {
		# host name matches prefix in conig but not the current host name 
		my $hname = $myHostNameFull;
		$hname =~ s/$myHostName/$k/;
		$additions = $additions . $IPAddresses{$k} . " " . $hname . " " . $k . "\n"
	}
}

system ("sudo su");
print "system call sudo su ... \n\n";

open my $hosts,'<','/etc/hosts'      or die "/etc/hosts: $!";
open my $new,  '>','/etc/hosts.new'  or die "/etc/hosts.new: $!";
while (<$hosts>) {
	chomp;
	my ($ip, $fullName, $name) = split /\s+/;
	last if /^## Added by.+setup\.pl/;
   		print $new $_,"\n"; 
}
print $new "## Added by bin/setup.pl\n";
print $new $additions ."\n";
close $new;
rename '/etc/hosts.new','/etc/hosts';