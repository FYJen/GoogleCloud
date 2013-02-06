#!/usr/bin/perl

use strict;
use warnings;

sub install_language_package {
	
	system ("sudo apt-get update");
	system ("sudo apt-get install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");

}

install_language_package;