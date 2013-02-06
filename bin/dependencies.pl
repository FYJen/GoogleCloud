#!/usr/bin/perl

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

sub install_java{
	system ("sudo apt-get -y install openjdk-6-jre");
}



install_language_package;
install_git;