#!/bin/bash



#Language package installation
#=============================== 

function install_language_package ( )
{

	sudo apt-get update
	sudo apt-get install language-pack-en-base
	sudo /usr/sbin/locale-gen en_IN.UTF-8
	sudo /usr/sbin/update-locale LANG=en_IN.UTF-8

}


#Function Calls
#====================

install_language_package 

