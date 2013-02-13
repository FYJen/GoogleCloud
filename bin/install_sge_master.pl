#!/usr/bin/perl

use strict;
use warnings;


#Global Variables:
#===============================

# System envrionment variables
my $host_name = `hostname`;
chomp($host_name);

# SGE tmp queue file name
my $queue_file = "new_queue.txt";
# SGE queue's name
my $queue_name = "GC_main.q";
# SGE tmp exe_host file name
my $exe_file = "exe_host.txt";

# Number of cores 
my $TotalCores = shift;
my $ReserCores = $TotalCores - 1;

# Local user
my $local_user = shift;
chomp($local_user);

# Number of arguements 
my $num_arg = $#ARGV + 1;
my @arg = ();
# Read in arguments and put them into an array
for (my $i = 0; $i < $num_arg; $i++) {
        my $input = shift;
        push(@arg, $input);
}

# Functions
#======================================

#
# Purpose: edit SGE config files
# Parameters: file_name, find_string, replace_string
#
sub edit_file {
	
	my $file_name = shift;
	my $find_string = shift;
	my $replace_string = shift;

	open (FILE, "+<$file_name");
	my @file = <FILE>;

	seek (FILE, 0, 0);

	foreach my $line (@file) {
        $line =~ s/$find_string/$replace_string/g;
        print FILE $line;
	}
	close FILE;
}

#
# Purpose: generate template from existing SGE config file
# Parameters: $file_name
#
sub generate_template {
	
	my $file_name = shift;
	open my $in, '<', $file_name or die "Can't read old file: $!";
	open my $out, '>', "$file_name.new" or die "Can't read new file: $!";
	while( <$in> ) {
    	next if /^(load_values|\s+)/;  # skip comment lines
    	last if /^processors/;  # stop at end of line starting with "processors"
    	print $out $_;
    }
    # print the rest of the lines	
	while( <$in> ) {
    	print $out $_;
	}
	close $out;
	rename "$file_name.new", "$file_name";
}



# Function call: Install SGE on Master node
#===================================================

# Install general package
	system ("sudo apt-get update");
	system ("sudo apt-get -y install language-pack-en-base");
	system ("sudo /usr/sbin/locale-gen en_IN.UTF-8");
	system ("sudo /usr/sbin/update-locale LANG=en_IN.UTF-8");
	
# Install Git
	system ("sudo apt-get -y install git");

# Install JAVA
	system ("sudo apt-get -y install openjdk-6-jre");
# Install SGE packages
	system ("sudo apt-get -y install gridengine-client gridengine-qmon gridengine-exec gridengine-master");
# Start SGE
	system ("sudo /etc/init.d/gridengine-exec start");

# Configure SGE 
# Add local user to admin 
	system ("sudo qconf -am $local_user");
	system ("qconf -au $local_user users");

# Add a host group
	system ("echo \"group_name \@allhosts\nhostlist NONE\" > host_group");
	system ("qconf -Ahgrp host_group");


# Add execution hosts
	system ("qconf -se $host_name >> $exe_file 2>>/dev/null");
	generate_template($exe_file);
	# Set initial $find_string variable
	my $find_string = $host_name;
	#Use the template to add all the exec hosts.
	foreach my $k (@arg) {
		# master_node is already an exec hosts so we don't need to add it
		if ($k ne $host_name) {
			edit_file($exe_file, $find_string, $k);
			system ("qconf -Ae $exe_file 2>> /dev/null");
			$find_string = $k;
		}
	}

# Configure submission and execution hosts 	
	foreach my $k (@arg) {
	  # Add every compute node as a submission host
		system ("qconf -as $k");
	  # Add exec host to the @allhosts list
		system ("qconf -aattr hostgroup hostlist $k \@allhosts");
	} 

# Create Queue
	system ("qconf -sq > $queue_file");
	# Open new_queue file and edit queue name
	edit_file($queue_file, "template", $queue_name);
	system ("qconf -Aq $queue_file");

# Add host group to a queue
	system ("qconf -aattr queue hostlist \@allhosts $queue_name");

# Configure reserved cpu on master node
	system ("qconf -aattr queue slots \"$TotalCores, [$host_name=$ReserCores]\" $queue_name");



