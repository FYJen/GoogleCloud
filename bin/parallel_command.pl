#!/usr/bin/perl 

use Data::Dumper;
use strict;
use warnings;
use Parallel::ForkManager;

# we need at least 2 arguments 
my $num_args = $#ARGV + 1;
if ($num_args < 2) {
	usage();
	exit(1);
}

my @instanceNames = "qtrinh1000 qtrinh1001 qtrinh1002 qtrinh1003 qtrinh1004";
my $num_of_nodes = length(@instanceNames);
my $instancePrefix = "qtrinh";
my $zone = "us-central1-a";

sub do_command {

	my @instanceNames = @$array;
	my $instancePrefix = shift;
	my $zone = shift;
	my $path = shift;
	my $num_of_nodes = shift;
	
	my $pm = Parallel::ForkManager->new($num_of_nodes);

	foreach my $k (@instanceNames) {
		$pm->start and next;

		#system ("gcutil ssh $k 'cat | perl /dev/stdin $path' < bin/mount_ephemeral.pl ");
		

		$pm->finish;
	}

	$pm->wait_all_children();

	print "\n\ndone ...\n\n";

}

