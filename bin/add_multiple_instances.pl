#!/usr/bin/perl

use warnings;
use strict;


# Global Variables:
#=============================================================

# System envrionment variables
my $host_name = `hostname`;
chomp($host_name);
# SGE tmp exe_host file name
my $exe_file = "exe_host.txt";
# Local user
my $local_user = shift;
chomp($local_user);



# Function Calls
#=============================================================
foreach my $k (@ARGV) {
	# Add the addition instance to submission host list
	system ("qconf -as $k");

# Add the addition instnace to execution host list
	system ("qconf -se $host_name >> $exe_file 2>>/dev/null");
	generate_template($exe_file);
	# Set initial $find_string variable
	my $find_string = $host_name;
	#Use the template 
	edit_file($exe_file, $find_string, $k);
	system ("qconf -Ae $exe_file 2>> /dev/null");

# Add exec host to the @allhosts list
	system ("qconf -aattr hostgroup hostlist $k \@allhosts");
}




# Functions
#=============================================================

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




