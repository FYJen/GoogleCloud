#!/usr/bin/perl

use Data::Dumper;
use strict;
use warnings;

my local_user = `users`;
chomp($local_user);
my num_arg = $#ARGV + 1;
my @arg = ();

# Read in arguments and put them into array
for (my $i = 0; $i < $num_arg; $i++) {
        my $input = shift;
        push(@arg, $input);
}


sub install_sge_master {

	# Install general package
	system ("sudo apt-get update");
	system ("sudo apt-get -y install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");
	system ("sudo apt-get -y install git")

	# Install JAVA
	system ("sudo apt-get -y install openjdk-6-jre");
	# Install SGE packages
	system ("sudo apt-get -y install gridengine-client gridengine-qmon gridengine-exec gridengine-master");
	# Start SGE
	system ("sudo /etc/init.d/gridengine-exec start");

	# Configure SGE
	system ("sudo su");
	system ("sudo -u sgeadmin qconf -am $local_user");
	system ("exit");
	system ("qconf -au $local_user users");
	  # Add every compute node as a submission host
	foreach my $k (@arg) {
		system ("qconf -as $k");
	}


}

install_sge_master;