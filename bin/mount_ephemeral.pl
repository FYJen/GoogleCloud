#!/usr/bin/perl 

use strict;
use warnings;

my $path = $ARGV[0];


sub mount_ephemeral_disk {

	my @DiskList = `ls -al /dev/disk/by-id/google-ephemeral-disk-* | cut -d ' ' --fields=9`;
	my $Num_Disk = @DiskList;
	my $disk = "";

	for (my $i = 0; $i < $Num_Disk; $i++) {
		
		#trim traling newline characters
		$DiskList[$i] =~ s/\n+$//;

		#$path = "/mnt/scratch";
		my $p = "$path$i";
		system("sudo mkdir -p $p");
		system("sudo chmod a+w $p");
		system("sudo /usr/share/google/safe_format_and_mount -m \"mkfs.ext4 -F\" $DiskList[$i] $p");
	}
}

mount_ephemeral_disk;
