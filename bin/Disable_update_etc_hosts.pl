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

=head
	my $iNames_table = Dumper(\%instanceNames);
	my $IP_table = Dumper(\%IPAddresses);

	while (my ($k,$v) = each %instanceNames) {
		system ("ssh $k perl -s < bin/update_etc_hosts.pl $iNames_table $instancePrefix $IP_table");
	}
=cut

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