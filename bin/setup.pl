#!/usr/bin/perl 

use Data::Dumper;
use strict;
use warnings;

my $MODE_INSTANCES_CREATE = 1;
my $MODE_INSTANCES_DELETE = 2;
my $MODE_UPDATE_ETC_HOSTS = 3;

my $num_args = $#ARGV + 1;
if ($num_args != 2) {
	print "\n";
	print "\nThis script creates and deletes Google Cloud instances";
	print "\n\nUsage: $0 [ FILE ] [ INT ] ";
	print "\n\n\t[FILE]\t\tconfig file";
	print "\n\t[INT]\t1\tcreate instances based on the input configuration file";
	print "\n\t\t2\tdelete instances based on the instance prefix defined in the input configuration file";
	print "\n\t\t3\tupdate /etc/hosts files for SGE installation";
	print "\n\n";
	exit (0);
}

my $configFile = $ARGV[0];
my $mode = $ARGV[1];

my ($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances) = parseConfigFile($configFile);

# for debugging 
print "\n\n";
print "\nzone $zone";
print "\nami $ami";
print "\ninstanceType $instanceType";
print "\ninstanceNamePrefix $instanceNamePrefix";
print "\nnumberOfInstances $numberOfInstances";
print "\n\n";

my %instanceNames = getInstanceNames();

if ($mode == $MODE_INSTANCES_DELETE) {
	deleteInstances(\%instanceNames, $instanceNamePrefix);
} elsif ($mode == $MODE_INSTANCES_CREATE) {
	createInstances($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances);
} elsif ($mode == $MODE_UPDATE_ETC_HOSTS) {
	updateEtcHosts(\%instanceNames, $instanceNamePrefix);
}


#
# get the list of running instances
#
sub getInstanceNames {

	my %iNames = ();
	# query to get list of running of instances 
	my @names = `gcutil listinstances | grep project | awk '{ print \$2 }'`;
	foreach my $n (@names) {
		# trim whitespaces 
		$n =~ s/^\s+//;
		$n =~ s/\s+$//;
		$iNames{$n} = 1;
	}
	while (my ($k,$v) = each %iNames){
		print "\nRunning instances '$k' ";
	}
	return %iNames;
}


#
# parse input config file
#
sub parseConfigFile {
	
	#assign config filename, open and read its contents into an array
	my $configFileName = shift ;
	my @line;
	my @options;

	open FILE, $configFileName or die "Could not find ${configFileName}\n";
	@options = <FILE>;

	#more options maybe added later in configuration file following format of:
	#	label: value
	foreach my $i (@options) {
		@line = split(" ", $i);
		if($i =~ /^ZONE:/) {
			$zone = $line[1];	
		} elsif($i =~ /^AMI:/) {
			$ami = $line[1];	
		} elsif($i =~ /^INSTANCE_TYPE:/) {
			$instanceType = $line[1];	
		} elsif($i =~ /^INSTANCE_NAME_PREFIX:/) {
			$instanceNamePrefix = $line[1];	
		} elsif($i =~ /^NUMBER_OF_INSTANCES:/) {
			$numberOfInstances = $line[1];	
		}
	}
	close FILE;
	return ($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances);
}


# create instances
sub createInstances {

	# counter starting from 1000
	my $counter = 1000;
	my $machineName ;
	my $machineNames = "";
	my ($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances) = @_;
	for (my $n = 1; $n <= $numberOfInstances; $n++) {
		$machineName = $instanceNamePrefix . $counter ;
		$machineNames = $machineNames . $machineName . " ";
		$counter++;
	}
	print "\n\n\n====================================================\n";
	print "\ncreating instances $machineNames ... \n\n";
	system ("gcutil addinstance $machineNames --wait_until_running --machine_type=$instanceType --zone=$zone 2>&1 | tee instances.creation.log ");
}

# update /etc/hosts 
sub updateEtcHosts {
	my $htable = shift;
	my %instanceNames = %$htable;
	my $instancePrefix = shift;

	if (!keys %instanceNames) {
		print "\n\n\n====================================================\n";
		print "\nno running instances to delete ... \n\n";
		return ;
	}
	while (my ($k,$v) = each %instanceNames){
		if ($k =~ /$instancePrefix/) {
			print "\ninstances matches prefix in config '$k' ";
		}
	}
}

# 
#
#
sub deleteInstances {

	my $htable = shift;
	my %instanceNames = %$htable;
	my $instancePrefix = shift;

	if (!keys %instanceNames) {
		print "\n\n\n====================================================\n";
		print "\nno running instances to delete ... \n\n";
		return ;
	}

	my $instances = "";
	while (my ($k,$v) = each %instanceNames){
		if ($k =~ /$instancePrefix/) {
			$instances = $instances . $k . " ";
		}
	}
	print "\n\n\n====================================================\n";
	if (length($instances) > 0) {
		print "\ndeleting instances $instances ...\n\n";
		system ("gcutil deleteinstance -f $instances 2>&1 | tee instances.deletion.log ");
	} else {
		print "\nNo instances with prefix '$$instanceNamePrefix' exist ...";
	}
	print "\n\n";
}




sub create_mount_ephemeral {

=head 
ll /dev/disk/by-id/google-ephemeral-disk-*
sudo mkdir /mnt/scratch/
sudo /usr/share/google/safe_format_and_mount -m "mkfs.ext4 -F" /dev/disk/by-id/google-ephemeral-disk-0 /mnt/scratch
sudo chmod a+w /mnt/scratch
=cut 
}

