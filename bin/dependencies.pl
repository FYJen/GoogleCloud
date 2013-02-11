#!/usr/bin/perl

use Data::Dumper;
use strict;
use warnings;

sub general_package {
	
	system ("sudo apt-get update");
	system ("sudo apt-get -y install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");
	system ("sudo apt-get -y install git")

}



