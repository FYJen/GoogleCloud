#!/usr/bin/perl 

use Data::Dumper;
use strict;
use warnings;

my $MODE_INSTANCES_CREATE = 100;
my $MODE_INSTANCES_DELETE = 101;

# instance specific 
my $MODE_INSTALL_SGE = 200;
my $MODE_UPDATE_INSTANCE = 201;
my $MODE_UPDATE_ETC_HOSTS = 202;
my $MODE_MOUNT_EPHEMERAL_DISK = 203;

my $num_args = $#ARGV + 1;
if ($num_args != 2) {
	print "\n";
	print "\nThis script creates and deletes Google Cloud instances";
	print "\n\nUsage: $0 [ FILE ] [ INT ] ";
	print "\n\n\t[FILE]\t\tconfig file";
	print "\n\t[INT]\t$MODE_INSTANCES_CREATE\tcreate instances based on the input configuration file";
	print "\n\t\t$MODE_INSTANCES_DELETE\tdelete instances based on the instance prefix defined in the input configuration file";
	print "\n\t\t$MODE_INSTALL_SGE\tInstall Sung Grid Engine (SGE) to the instances created. ";
	print "\n\t\t$MODE_UPDATE_INSTANCE\tupdate packages on instance ";
	print "\n\t\t$MODE_UPDATE_ETC_HOSTS\tupdate /etc/host file on an instance for SGE installation";
	print "\n\t\t$MODE_MOUNT_EPHEMERAL_DISK\tMount ephemeral disk to individual server";
	print "\n\n";
	exit (0);
}

my $configFile = $ARGV[0];
my $mode = $ARGV[1];

my ($zone, $ami, $instanceType, $instanceCores, $instanceNamePrefix, $numberOfInstances) = parseConfigFile($configFile);

# for debugging 
print "\n\n";
print "\nzone $zone";
print "\nami $ami";
print "\ninstanceType $instanceType";
print "\ninstanceCores $instanceCores";
print "\ninstanceNamePrefix $instanceNamePrefix";
print "\nnumberOfInstances $numberOfInstances";
print "\n\n";

my %instanceNames = getInstanceNames();

if ($mode == $MODE_INSTANCES_DELETE) {
	deleteInstances(\%instanceNames, $instanceNamePrefix);
} elsif ($mode == $MODE_INSTANCES_CREATE) {
	createInstances($zone, $ami, $instanceType, $instanceNamePrefix, $numberOfInstances);
} elsif ($mode == $MODE_INSTALL_SGE) {
	SGE_install(\%instanceNames, $instanceNamePrefix);
}elsif ($mode == $MODE_UPDATE_INSTANCE) {
	updateInstance(\%instanceNames);
} elsif ($mode == $MODE_UPDATE_ETC_HOSTS) {
	updateEtcHosts(\%instanceNames, $instanceNamePrefix);
} elsif ($mode == $MODE_MOUNT_EPHEMERAL_DISK) {
	create_mount_ephemeral(\%instanceNames, $instanceNamePrefix);
}

#
#
#
sub SGE_install {

	my $htable = shift;
	my %instanceNames = %$htable;
	my $instanceNamePrefix = shift; 


	#Install SGE on master node
	#===================================
	my $master_node = `hostname`;
	# Update /etc/hosts file on master node
	updateEtcHosts(\%instanceNames, $instanceNamePrefix);
	install_package("java");
	install_package("SGE_Master");


	#Install SGE on Compute node
	#=================================
	#Update /etc/hosts file on every node
	while (my ($k,$v) = each %instanceNames) {
		
	}
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
		if ($n =~ /$instanceNamePrefix/) {
			$iNames{$n} = 1;	
		}
	}
	while (my ($k,$v) = each %iNames){
		print "\nRunning instances '$k' \n";
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
		} elsif($i =~ /^INSTANCE_CORES:/){
			$instanceCores = $line[1];
		} elsif($i =~ /^INSTANCE_NAME_PREFIX:/) {
			$instanceNamePrefix = $line[1];	
		} elsif($i =~ /^NUMBER_OF_INSTANCES:/) {
			$numberOfInstances = $line[1];	
		}
	}
	close FILE;
	return ($zone, $ami, $instanceType, $instanceCores, $instanceNamePrefix, $numberOfInstances);
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


#
# update /etc/hosts to include other hostnames and IP address
#
sub updateEtcHosts {
	my $htable = shift;
	my %instanceNames = %$htable;
	my $instancePrefix = shift;

	my %IPAddresses = getIPAddress($instancePrefix);
	

	if (!keys %instanceNames) {
		print "\n\n\n====================================================\n";
		print "\nno running instances to update /etc/hosts ... \n\n";
		return ;
	}
=head
	my $iNames_table = Dumper(\%instanceNames);
	my $IP_table = Dumper(\%IPAddresses);

	while (my ($k,$v) = each %instanceNames) {
		system ("ssh $k perl -s < bin/update_etc_hosts.pl $iNames_table $instancePrefix $IP_table");
	}
=cut

	# get current host name 
	my $myHostName = `hostname`;
	chomp($myHostName);
	my $myHostNameFull = `hostname -f `;
	chomp($myHostNameFull);

	# additions to be added to /etc/hosts
	my $additions = "";

	while (my ($k,$v) = each %instanceNames){
		if (($k =~ /^$instancePrefix/) && ($k ne $myHostName)) {
			# host name matches prefix in conig but not the current host name 
			my $hname = $myHostNameFull;
			$hname =~ s/$myHostName/$k/;
			$additions = $additions . $IPAddresses{$k} . " " . $hname . " " . $k . "\n"
		}
	}

	open my $hosts,'<','/etc/hosts'      or die "/etc/hosts: $!";
	open my $new,  '>','/etc/hosts.new'  or die "/etc/hosts.new: $!";
	while (<$hosts>) {
		chomp;
		my ($ip, $fullName, $name) = split /\s+/;
		last if /^## Added by.+setup\.pl/;
    		print $new $_,"\n"; 
	}
	print $new "## Added by bin/setup.pl\n";
 	print $new $additions ."\n";
	close $new;
	rename '/etc/hosts.new','/etc/hosts';

}

# 
# get IP address of all host with 'instanceNamePrefix
#
sub getIPAddress {

	my $instanceNamePrefix = shift;
	my %IP = ();
	my @data = `gcutil listinstances | grep project`;
	foreach my $line (@data) {
		my @fields = split (/\|/, $line);
		# trim leading and traling whitespaces 
		$fields[1] =~ s/^\s+//;
		$fields[1] =~ s/\s+$//;
		$fields[5] =~ s/^\s+//;
		$fields[5] =~ s/\s+$//;
		$IP{$fields[1]} = $fields[5]; 
	} 
	return %IP;
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

	my $htable = shift;
	my %instanceNames = %$htable;
	my $instancePrefix = shift;

	while (my ($k,$v) = each %instanceNames) {
		system ("gcutil ssh $k perl < bin/mount_ephemeral.pl");	
	}
	print "\n\nDone ...\n\n";

}

#
sub updateInstance {

	my $htable = shift;
	my %instanceNames = %$htable;

	while (my ($k,$v) = each %instanceNames) {
		system ("gcutil ssh $k perl < bin/dependencies.pl");	
	}

}

#
sub install_package {

	my $arg = shift;
	system ("sudo perl bin/dependencies.pl $arg");

}

#
sub make_internal_ssh_available {

}

#
sub SGE_filewall {
	system("gcutil addfirewall sge6444 --description=\"Incoming 6444 allowed.\" --allowed=\"tcp:6444\"");
	system("gcutil addfirewall sge6445 --description=\"Incoming 6445 allowed.\" --allowed=\"tcp:6445\"");
}

