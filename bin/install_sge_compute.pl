#!/usr/bin/perl

use Data::Dumper;
use strict;
use warnings;


my $master_node = $ARGV[0];
my $hostName = `hostname`;
chomp($hostName);
my $hostNameFull = `hostname -f`;
chomp($hostNameFull);

sub install_sge_compute {

	# Install general package
	system ("sudo apt-get update");
	system ("sudo apt-get -y install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");
	
	# Install Git
	system ("sudo apt-get -y install git");

	# Install JAVA
	system ("sudo apt-get -y install openjdk-6-jre");
	# Install Sun Grid Engin package
	system ("sudo apt-get -y install gridengine-client gridengine-exec");

	#Add master node to SGE act_qmaster file
	my $master_hostName = $hostNameFull;
	$master_hostName =~ s/$hostName/$master_node/; 
	system ("echo $master_hostName | sudo tee /var/lib/gridengine/default/common/act_qmaster");
	system ("sudo /etc/init.d/gridengine-exec start");
}

install_sge_compute;