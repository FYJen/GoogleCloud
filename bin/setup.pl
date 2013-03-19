#!/usr/bin/perl 

use Data::Dumper;
use strict;
use warnings;
use Parallel::ForkManager;

my $MODE_INSTANCES_CREATE = 100;

my $MODE_INSTANCES_DELETE = 101;

# instance specific 
my $MODE_MOUNT_EPHEMERAL_DISK = 102;
my $MODE_INSTALL_SGE = 201;
my $MODE_ADD_AN_INSTANCE = 202;


my $SGE_INSTALLATION_POSTFIX = "GoogleCloud.SGE.installation.log";

# we need at least 2 arguments 
my $num_args = $#ARGV + 1;
if ($num_args < 2) {
	usage();
	exit(1);
}

# Config file
my $configFile = $ARGV[0];

# Mode 
my $mode = $ARGV[1];

# parse the config file
my ($zone, $ami, $instanceType, $numberOfCores, $instanceNamePrefix, $numberOfInstances, $master_node, $compute_nodes) = parseConfigFile($configFile);

# Get a local user
my $local_user = $ENV{LOGNAME};

# Print out the attributes after pasing the config file.
# For debugging purpose 
print "\n";
print "\nZONE:\t\t\t$zone";
print "\nAMI\t\t\t$ami";
print "\nINSTANCE NAME PREFIX\t$instanceNamePrefix";
print "\nINSTANCE TYPE\t\t$instanceType [ $numberOfCores core(s) ]";
print "\nNUMBER OF INSTANCES\t$numberOfInstances [ total number of cores " . $numberOfInstances * $numberOfCores . " ]";
print "\n\n";


# Get all the running instances 
my @instanceNames = getInstanceNames($zone);
	
# Perform different functions according to function mode
if ($mode == $MODE_INSTANCES_DELETE) {
	# Delete instance
	deleteInstances(\@instanceNames, $instanceNamePrefix, $zone);
} elsif ($mode == $MODE_INSTANCES_CREATE) {
	# Create instance
	if (Check_Resources("instance", $numberOfInstances) && Check_Resources("cpu", $numberOfInstances*$numberOfCores)) {
		createInstances($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances);
	}
} elsif ($mode == $MODE_MOUNT_EPHEMERAL_DISK) {
	# Mount ephemeral disks
	if ($num_args != 3) {
		print "\n\nplease include path prefix to mount emepheral devices...\n";
		usage();
		exit (0);
	} 
	my $path = $ARGV[2];
	create_mount_ephemeral(\@instanceNames, $instanceNamePrefix, $zone, $path, $numberOfInstances );
} elsif ($mode == $MODE_INSTALL_SGE) {
	create_SGE(\@instanceNames, $configFile, $instanceNamePrefix, $numberOfCores, $local_user);
} elsif ($mode == $MODE_ADD_AN_INSTANCE) {
	if (Check_Resources("cpu", $numberOfInstances*$numberOfCores) && Check_Resources("instance", $numberOfInstances)) {
		createInstances($zone, $ami, $instanceType, $instanceNamePrefix, 1);
		@instanceNames = getInstanceNames($zone);
		update_SGE (\@instanceNames, "add", $local_user);
	}
} else {
	print "\n\n====================================================\n";
	print "\n\nInvalid input MODE!!!! Please see usage below\n";
	usage();
}


#
# usage 
#
sub usage {
	print "\n";
	print "\nThis script setup Google Cloud instances and Sun Grid Engine (SGE)";
	print "\n\nUsage: $0 [ FILE ] [ MODE ] ";
	print "\n\n\t[FILE]\t\tconfig file";
	print "\n\t[MODE]\t$MODE_INSTANCES_CREATE\tcreate instances based on the input configuration file";
	print "\n\t\t$MODE_INSTANCES_DELETE\tdelete all instances based on the instance prefix defined in the input configuration file";
	#print "\n\t\t$MODE_UPDATE_INSTANCE\tupdate packages on instance ";
	#print "\n\t\t$MODE_UPDATE_ETC_HOSTS\tupdate /etc/host file on an instance for SGE installation";
	print "\n\t\t$MODE_MOUNT_EPHEMERAL_DISK\tmount available ephemeral disk to individual instances";
	print "\n\t\t\t[PATH]\tpath prefix to mount ephemeral disk(s) to";
	print "\n";
	print "\n\t\t$MODE_INSTALL_SGE\tinstall Sun Grid Engine (SGE) on the instances created. ";
	print "\n\t\t$MODE_ADD_AN_INSTANCE\tadd additional instances to the SGE cluster. ";
	print "\n\n";
	exit (2);
}


#
# Check Resources
#
sub Check_Resources {

	my $property = shift;
	my $required_resource = shift;
	my $project_resources;
	my $current_resource;
	my $overall_resource;
	my $ diff;
	my @line;


	$project_resources = `gcutil getproject | grep $property | awk '{print \$4}'`;
	chomp($project_resources);
	$project_resources =~ s/\n\|$//;
	@line = split("/", $project_resources);
	$current_resource = $line[0];
	$overall_resource = $line[1];
	$diff = $overall_resource - $current_resource;

	if ($property =~ /instance/) {
		if ($diff >= $required_resource) {
			return 1;
		} else {
			print "\nPROBLEM [POSSIBLE QUOTA_EXCEED]:";
			print "\n\tThe project resources: $property\[$current_resource/$overall_resource\] is not enough to create the demanded instances";
			print "\n\tYou are asking a total of $required_resource instances, where only $diff is available\n\n";
		}
	} elsif ($property =~ /cpu/) {
		if ($diff >= $required_resource) {
			return 1;
		} else {
			print "\nPROBLEM [POSSIBLE QUOTA_EXCEED]:";
			print "\n\tThe project resources: $property\[$current_resource/$overall_resource\] is not enough to create the demanded instances";
			print "\n\tYou are asking a total of $required_resource cores, where only $diff is available\n\n";
		}
	}
	exit (2);

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
			my @fields = split ("-", $instanceType);
			$numberOfCores = $fields[2]; 
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
	return ($zone, $ami, $instanceType, $numberOfCores, $instanceNamePrefix, $numberOfInstances, $master_node, $compute_nodes);
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
		$counter = 1000;
		print FILE "$counter";
		close FILE;
		return $counter;
	}
}


#
# MODE_CODE: 100
# Create Instances
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
	print "\n\n====================================================\n";
	print "\ncreating instances $machineNames ... \n\n";
	if (length($ami)==0) {
		system ("gcutil addinstance $machineNames --wait_until_running --machine_type=$instanceType --zone=$zone 2>&1 | tee  $instanceNamePrefix.instances.creation.log ");
	} else {
		system ("gcutil addinstance $machineNames --image=$ami --wait_until_running --machine_type=$instanceType --zone=$zone 2>&1 | tee $instanceNamePrefix.instances.creation.log ");
	}

	#update new counter to file.
	open (FILE, ">.$instanceNamePrefix.counter.txt") || die "Cannot open file: $!\n";
	print FILE "$counter";
	close FILE;
}


# 
# MODE_CODE: 101
# Delete all instances based on the instance prefix 
# defined in the input configuration file
#
sub deleteInstances {

	my $array = shift;
	my @instanceNames = @$array;
	my $instancePrefix = shift;
	my $zone = shift;

	my $num_instance = @instanceNames;
	if ( $num_instance == 0) {
		print "\n\nNo running instances with prefix - $instancePrefix exist ...\n\n";
		return ;
	}

	my $instances = "";
	foreach my $k (@instanceNames){
		$instances = $instances . $k . " ";
	}
	print "\n\n====================================================\n";
	if (length($instances) > 0) {
		print "\ndeleting instances $instances ...\n\n";
		system ("gcutil deleteinstance --zone=$zone -f $instances 2>&1 | tee  $instanceNamePrefix.instances.deletion.log ");
		print "\n\ndone deleting instances $instances\n\n";
	}
	#remove counter file
	unlink(".$instanceNamePrefix.counter.txt");
	unlink("*.$SGE_INSTALLATION_POSTFIX");
	print "\n\n";
}


#
# Get the list of running instances and put them into array.
#
sub getInstanceNames {

	my $zone = shift;

	my @iNames = ();
	# query to get list of running of instances 
	# my @names = `gcutil listinstances --zone=$zone | grep project | awk '{ print \$2 }'`;
	my @names = `gcutil listinstances --zone=$zone | grep network | awk '{ print \$2 }'`;
	foreach my $n (@names) {
		# trim whitespaces 
		$n =~ s/^\s+//;
		$n =~ s/\s+$//;
		if ($n =~ /$instanceNamePrefix/) {
			push(@iNames, $n);
		}
	}
	if (scalar(@iNames) > 0) {
		print "====================================================\n\n";
		foreach my $k (@iNames){
			print "Running instances '$k' \n\n";
		}
	}
	return @iNames;
}


#
# MODE_CODE: 102
# Mount ephemeral disks
#
sub create_mount_ephemeral {

	my $array = shift;
	my @instanceNames = @$array;
	my $instancePrefix = shift;
	my $zone = shift;
	my $path = shift;
	my $num_of_nodes = shift;
	
	my $pm = Parallel::ForkManager->new($num_of_nodes);

	foreach my $k (@instanceNames) {
		$pm->start and next;
		system ("gcutil ssh $k 'cat | perl /dev/stdin $path' < bin/mount_ephemeral.pl ");	
		$pm->finish;
	}

	$pm->wait_all_children();

	print "\n\ndone ...\n\n";

}

#
# Check if SGE is installed or not
# check_sge: $master_node
#
sub check_sge {

	my $master_node = shift;

	my @output = `gcutil ssh $master_node 'ps aux | grep sge | cut --delimiter=" " --field=1 | head -2'`;
	my $num_ele = @output;

	if ($num_ele == 2) {
		chomp($output[0]);
		chomp($output[1]);
		if ($output[0] eq "sgeadmin" && $output[1] eq "sgeadmin") {
			return;
		} else {
			print "\nSGE is not installed and configured on master node - $master_node.\nPlese run the script with mode = 201\n";
			print "Abort ... \n";
			exit (2);
		}
	} else {
		print "\nSGE is not installed and configured on master node - $master_node\nPlese run the script with mode = 201\n";
		print "Abort ... \n";
		exit (2);
	}
}


#
# MODE_CODE: 201
# Remotely installing SGE 
#
sub installingSGE {

	my $action = shift;
	my $target = shift;
	my $arg = shift;

	if ($action eq "master") {
		print "Installing SGE on master node -  $target ... it may take a few minutes ... \n\n";
		system ("gcutil ssh $target 'cat | perl /dev/stdin $arg' < bin/install_sge_master.pl &> $target.$SGE_INSTALLATION_POSTFIX");
		print "SGE master node  \($target\) installation ... done ...\n\n";
	} else {
		# Action = compute
		print "Installing SGE on compute node - $target ... it may take a few minutes ... \n\n";
		system ("gcutil ssh $target 'cat | perl /dev/stdin $arg' < bin/install_sge_compute.pl &> $target.$SGE_INSTALLATION_POSTFIX");
		print "SGE compute node \($target\) installation ... done ...\n\n";
	}
}



#
# Purpose: Create SGE 
# Parameters: @instanceNames, $configFile, $instanceNamePrefix, $numberOfCores $local_user
# 
sub create_SGE {
	
	my $array = shift;
	my @instanceNames = @$array;
	my $configFile = shift;
	my $instanceNamePrefix = shift;
	my $numberOfCores = shift;
	my $local_user = shift; 

	# Assign master and compute nodes	
	my $master_node = $instanceNames[0];
	my $compute_nodes = "";
	# Set number of compute nodes
	my $num_of_node = @instanceNames;


	# Initiate FORK
	my $pm = Parallel::ForkManager->new($num_of_node);

	# Check the number of cores before attempting the installation.
	# Number of cores need to be greater or equal to 2.
	if ($numberOfCores <= 1) {
		print "\n\n====================================================\n";
		print "\nThe instance type - \"$instanceType\" is not suitable for SGE (number of cores needs >= 2)...\n\n";
		exit (2) ;
	}
	
	# Check the number of instances.
	my $num_instance = @instanceNames;
	if ( $num_instance == 0) {
		print "\n\n====================================================\n";
		print "\nNo runing instances with prefix - \"$instanceNamePrefix\" exist to install SGE...\n\n";
		exit (2) ;
	}


	foreach my $k (@instanceNames) {
		
		# Fork starts
		$pm->start and next;

		if ($k eq $master_node) {	
			my @cNode = @instanceNames;
			# Join the elements from an array and return a scalar
			my $node_list = join(" ", @cNode);
			my $cores_node_list = $numberOfCores." ".$local_user." ".$node_list;
			
			installingSGE("master", $k, $cores_node_list);

		} elsif ($num_of_node != 1) {
			# Collect compute nodes
			$compute_nodes = $compute_nodes.$k." ";
			installingSGE("compute", $k, $master_node);
		} else {
			return;
		}
		
		# Fork finishes 
		$pm->finish;

	}
	$pm->wait_all_children;
	
=head
	# Write master_node and compute_nodes to config.txtfile
	open (FILE, ">>$configFile") or die "Could not find ${configFile}: $!\n";
	print FILE "\nMASTER_NODE: $master_node\n";
	print FILE "COMPUTE_NODES: $compute_nodes\n\n";
	close(FILE);
=cut
}


#
# Add an instance as a node 
#
sub update_SGE {

	# List of my instanceNames
	my $array = shift;
	my @instanceNames = @$array;
	# Process the instanceNames list 
	my $master_node = $instanceNames[0]; # We make first element as our master_node. 
	my $index = $#instanceNames; # Get the index of the last element because it is the new added node
	my $target_node = $instanceNames[$index];

	# What action it is (add/delete)
	my $action = shift;
	# Local user
	my $local_user = shift;

	# Check for SGE installation
	check_sge($master_node);

	#Combine variables
	my $arg = $local_user." ".$target_node;

	if ($action eq "add") {
		system ("gcutil ssh $master_node 'cat | perl /dev/stdin $arg' < bin/add_an_instance.pl");
		system ("gcutil ssh $target_node 'cat | perl /dev/stdin $master_node' < bin/install_sge_compute.pl");
	} else { 
		system ("gcutil deleteinstance -f $target_node 2>&1 | tee instances.deletion.log");

	}
	
}


#
# MODE_CODE: 202
# Add extra instances
#
sub add_instance {
	
}


