#!/usr/bin/perl 

use Data::Dumper;
use strict;
use warnings;

my $MODE_INSTANCES_CREATE = 100;
my $MODE_INSTANCES_DELETE = 101;

# instance specific 
my $MODE_MOUNT_EPHEMERAL_DISK = 200;
my $MODE_INSTALL_SGE = 201;
my $MODE_ADD_AN_INSTANCE = 202;

my $num_args = $#ARGV + 1;
if ($num_args != 2) {
	print "\n";
	print "\nThis script creates and deletes Google Cloud instances";
	print "\n\nUsage: $0 [ FILE ] [ INT ] ";
	print "\n\n\t[FILE]\t\tconfig file";
	print "\n\t[INT]\t$MODE_INSTANCES_CREATE\tcreate instances based on the input configuration file";
	print "\n\t\t$MODE_INSTANCES_DELETE\tdelete all instances based on the instance prefix defined in the input configuration file";
	#print "\n\t\t$MODE_UPDATE_INSTANCE\tupdate packages on instance ";
	#print "\n\t\t$MODE_UPDATE_ETC_HOSTS\tupdate /etc/host file on an instance for SGE installation";
	print "\n\t\t$MODE_MOUNT_EPHEMERAL_DISK\tMount ephemeral disk to individual server";
	print "\n\t\t$MODE_INSTALL_SGE\tInstall Sung Grid Engine (SGE) to the instances created. ";
	print "\n\t\t$MODE_ADD_AN_INSTANCE\tAdd an extra instance to SGE cluster. ";
	print "\n\n";
	exit (0);
}

# Read the config file
my $configFile = $ARGV[0];
# Read the function code
my $mode = $ARGV[1];
# Parse the config file
my ($zone, $ami, $instanceType, $instanceCores, $instanceNamePrefix, $numberOfInstances, $master_node, $compute_nodes) = parseConfigFile($configFile);
# Get a local user
my $local_user = $ENV{LOGNAME};

# Print out the results after pasing the config file.
# Also for debugging purpose 
print "\n\n";
print "\nzone $zone";
print "\nami $ami";
print "\ninstanceType $instanceType";
print "\ninstanceCores $instanceCores";
print "\ninstanceNamePrefix $instanceNamePrefix";
print "\nnumberOfInstances $numberOfInstances";
print "\n\n";

# Get all the running instance
my @instanceNames = getInstanceNames();

# Preform different functions accodring to function codes
if ($mode == $MODE_INSTANCES_DELETE) {
	# Delete instance
	deleteInstances(\@instanceNames, $instanceNamePrefix);
} elsif ($mode == $MODE_INSTANCES_CREATE) {
	# Create instance
	createInstances($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances);
} elsif ($mode == $MODE_MOUNT_EPHEMERAL_DISK) {
	# Mount ephemeral disks
	create_mount_ephemeral(\@instanceNames, $instanceNamePrefix);
} elsif ($mode == $MODE_INSTALL_SGE) {
	create_SGE(\@instanceNames, $configFile, $instanceNamePrefix, $instanceCores, $local_user);
} elsif ($mode == $MODE_ADD_AN_INSTANCE) {
	createInstances($zone, $ami, $instanceType, $instanceNamePrefix, 1);
	@instanceNames = getInstanceNames();
	update_SGE (\@instanceNames, "add", $local_user);
} else {
	print "\n\n====================================================\n";
	print "\nInvalid MODE has been assigned ... \n\n";
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
		} elsif($i =~ /^INSTANCE_CORES:/){
			$instanceCores = $line[1];
		} elsif($i =~ /^INSTANCE_NAME_PREFIX:/) {
			$instanceNamePrefix = $line[1];	
		} elsif($i =~ /^NUMBER_OF_INSTANCES:/) {
			$numberOfInstances = $line[1];	
		} elsif($i =~ /^MASTER_NODE:/) {
			$master_node = $line[1];
		} elsif($i =~ /^COMPUTE_NODES:/){
			$compute_nodes = $line[1];
		}
	}
	close FILE;
	return ($zone, $ami, $instanceType, $instanceCores, $instanceNamePrefix, $numberOfInstances, $master_node, $compute_nodes);
}

#
# Read the counter 
#
sub  read_counter {
	
	my $filename = shift;
	my $counter;

	if (-e $filename) {
		open FILE, $filename or die "Could not open ${filename}: $!\n";
		my @line = <FILE>;
		foreach my $i (@line) {
			$counter = $i;
		}
		close FILE;
		chomp($counter);
		return $counter;
	} else {
		open (FILE, ">$filename") || die "Cannot open file: $!\n";
        print FILE "1000";
        close FILE;
        $counter = 1000;
        return $counter;
    }
}

#
# create instances
#
sub createInstances {

	my ($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances) = @_;
	# counter starting from 1000
	my $counter = read_counter(".$instanceNamePrefix.counter.txt");
	my $machineName ;
	my $machineNames = "";
	for (my $n = 1; $n <= $numberOfInstances; $n++) {
		$machineName = $instanceNamePrefix . $counter ;
		$machineNames = $machineNames . $machineName . " ";
		$counter++;
	}
	#update new  to file.
	open (FILE, ">.$instanceNamePrefix.counter.txt") || die "Cannot open file: $!\n";
	print FILE "$counter";
	close FILE; 
	print "\n\n====================================================\n";
	print "\ncreating instances $machineNames ... \n\n";
	system ("gcutil addinstance $machineNames --wait_until_running --machine_type=$instanceType --zone=$zone 2>&1 | tee instances.creation.log ");
}


# 
# delete all instances based on the instance prefix 
# defined in the input configuration file
#
sub deleteInstances {

	my $array = shift;
	my @instanceNames = @$array;
	my $instancePrefix = shift;

	my $num_instance = @instanceNames;
	if ( $num_instance == 0) {
		print "\n\n\n====================================================\n";
		print "\nNo runing instances with prefix - $instancePrefix exist ...\n\n";
		return ;
	}

	my $instances = "";
	foreach my $k (@instanceNames){
		$instances = $instances . $k . " ";
	}
	print "\n\n====================================================\n";
	if (length($instances) > 0) {
		print "\ndeleting instances $instances ...\n\n";
		system ("gcutil deleteinstance -f $instances 2>&1 | tee instances.deletion.log ");
	}
	#remove counter file
	unlink(".$instanceNamePrefix.counter.txt");
	print "\n\n";
}


#
# Get the list of running instances and put them into array.
#
sub getInstanceNames {

	my @iNames = ();
	# query to get list of running of instances 
	my @names = `gcutil listinstances | grep project | awk '{ print \$2 }'`;
	foreach my $n (@names) {
		# trim whitespaces 
		$n =~ s/^\s+//;
		$n =~ s/\s+$//;
		if ($n =~ /$instanceNamePrefix/) {
			push(@iNames, $n);
		}
	}
	foreach my $k (@iNames){
		print "\nRunning instances '$k' \n";
	}
	return @iNames;
}

#
# Mount ephemeral disks
#
sub create_mount_ephemeral {

	my $array = shift;
	my @instanceNames = @$array;
	my $instancePrefix = shift;

	foreach my $k (@instanceNames) {
		system ("gcutil ssh $k perl < bin/mount_ephemeral.pl");	
	}
	print "\n\nDone ...\n\n";

}

#
# Purpose: Create SGE 
# Parameters: @instanceNames, $configFile, $instanceNamePrefix, $instanceCores
#
sub create_SGE {
	
	my $array = shift;
	my @instanceNames = @$array;
	my $configFile = shift;
	my $instanceNamePrefix = shift;
	my $instanceCores = shift;
	my $local_user = shift; 

	# Check the number of cores before attempting the installation.
	# Number of cores need to be greater or equal to 2.
	if ($instanceCores <= 1) {
		print "\n\n====================================================\n";
		print "\nThe instance type - \"$instanceType\" is not suitable for SGE (number of cores needs >= 2)...\n\n";
		return ;
	}
	
	# Check the number of instances.
	my $num_instance = @instanceNames;
	if ( $num_instance == 0) {
		print "\n\n====================================================\n";
		print "\nNo runing instances with prefix - \"$instanceNamePrefix\" exist to install SGE...\n\n";
		return ;
	}

	# Assign master and compute nodes	
	my $master_node = $instanceNames[0];
	my $compute_nodes = "";

	foreach my $k (@instanceNames) {
		
		if ($k eq $master_node) {	
			my @cNode = @instanceNames;
			# Join the elements from an array and return a scalar
			my $node_list = join(" ", @cNode);
			my $cores_node_list = $instanceCores." ".$local_user." ".$node_list;
			
			system ("gcutil ssh $k 'cat | perl /dev/stdin $cores_node_list' < bin/install_sge_master.pl");
		} else {
			# Collect compute nodes
			$compute_nodes = $compute_nodes.$k." ";
			# Pass hostname to the script from local to remote and execute the script
			system ("gcutil ssh $k 'cat | perl /dev/stdin $master_node' < bin/install_sge_compute.pl");
		}

	}

	# Write master_node and compute_nodes to config.txtfile
	open (FILE, ">>$configFile") or die "Could not find ${configFile}: $!\n";
	print FILE "\nMASTER_NODE: $master_node\n";
	print FILE "COMPUTE_NODES: $compute_nodes\n\n";
	close(FILE);

}


#
# Add an instance as a node 
#
sub update_SGE {

	# List of my instanceNames
	my $array = shift;
	my @instanceNames = @$array;
	# Process the instanceNames list 
	my $master_node = $instanceNames[0]; # First element is master_node
	my $index = $#instanceNames; # Get the index of the last element as it is the new added node
	my $action_node = $instanceNames[$index];

	# What action it is (add/delete)
	my $action = shift;
	# Local user
	my $local_user = shift;

	#Combine variables
	my $arg = $local_user." ".$action_node;

	if ($action eq "add") {
		system ("gcutil ssh $master_node 'cat | perl /dev/stdin $arg' < bin/add_an_instance.pl");
		system ("gcutil ssh $action_node 'cat | perl /dev/stdin $master_node' < bin/install_sge_compute.pl");
	} else { 
		system ("gcutil deleteinstance -f $action_node 2>&1 | tee instances.deletion.log");

	}
	
}



