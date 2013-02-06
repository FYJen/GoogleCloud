#!/usr/bin/perl

use Data::Dumper;
use strict;
use warnings;

my $arg = $ARGV[0];


sub install_language_package {
	
	system ("sudo apt-get update");
	system ("sudo apt-get -y install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");

}

sub install_git {
	system ("sudo apt-get -y install git")
}

sub install_java {
	system ("sudo apt-get -y install openjdk-6-jre");
}

sub install_sge_master {
	system ("sudo apt-get install gridengine-client gridengine-qmon gridengine-exec gridengine-master");
}


if ($arg eq "java") {
	install_java;
} elsif ($arg eq "SGE_Master"){
	install_sge_master;
}else {
	install_language_package;
	install_git;
}

