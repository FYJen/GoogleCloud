SGE Installation
================

This is a basic SGE installation guildline on Google Cloud.

Setup: 
	
* One master node and one comput node (Two VMs)
* Ports: 6444, 6445

Steps
----------

**Step 1:** Make sure you follow /doc/getting.started.with.Google.Cloud.md to "Add firewall. ..."

**Setp 2:** Add two more firewall rules to our default network.

* gcutil addfirewall sge6444 --description="Incoming 6444 allowed." --allowed="tcp:6444"

* gcutil addfirewall sge6445 --description="Incoming 6445 allowed." --allowed="tcp:6445"

**Setp 3:** Create Instance.

* Image        : ubuntu-10-04-v2012-912
* Machine Type : n1-standard-4-d (https://cloud.google.com/pricing/compute-engine)
* Zone         : us-east1-a
	
	Use the google_create.sh to create instances. (instance_name is required as arugement)

		. google_create.sh "instance-name"
	
	We will need two instances. For example,

		.google_create.sh ajen01
		.google_create.sh ajen02

**Step 4:** Install prerequisites for SGE

Logon to two instances either by gcutil or ssh. 

* switch to admin user
		
		sudo su

* Edit /ect/hosts file 

		1. Master node needs an entries of Compute node's
		2. Comput node needs an entries of Master node's 
	
* For example:
		
		Master:
		127.0.0.1 localhost
		169.254.169.254 metadata.google.internal metadata
		10.240.59.34 ajen02.c.qtrinhcloud.internal ajen02
		10.240.81.31 ajen01.c.qtrinhcloud.internal ajen01  # Added by Google
	
		Compute:
		127.0.0.1 localhost
		169.254.169.254 metadata.google.internal metadata
		10.240.81.31 ajen01.c.qtrinhcloud.internal ajen01
		10.240.59.34 ajen02.c.qtrinhcloud.internal ajen02  # Added by Google

		
		** Basically, it copies the line that is added by Google and pastes to others.

* Update source.list
	
		apt-get update 

* Install language package (optional; however, it will be really messy when we are insatlling packages through apt-get becasue some warrning messages will get thrown.)

		apt-get install language-pack-en-base
		/usr/sbin/locale-gen en_IN.UTF-8
		/usr/sbin/update-locale LANG=en_IN.UTF-8

* Install Java

		apt-get install openjdk-6-jre
	
Replicate step 4 on both master and compute nodes. 

(Will prepare an auto-install script.)

**Step 5:** Install SGE

* On Master node do: 

		apt-get install gridengine-client gridengine-qmon gridengine-exec gridengine-master
	
	It might throw error message saying that there is a communication error. For example,
	
		critical error: abort qmaster registration due to communication errors
		daemonize error: child exited before sending daemonize state
	
	No worries, it might cause by java or previous left-over installation. Check the process, 
		
		ps aux | grep sge
	
	To see if gridengine-exec is started or not. If there is only gridengine-master, then start gridengine-exec then restart the gridengine-master
	
		/etc/init.d/gridengine-exec start
		/etc/init.d/gridengine-master restart
	
	However, if there already exists gridengine-exec, then kill it, then start it again. 
		
		kill -9 "ID"
		/etc/init.d/gridengine-exec start
		/etc/init.d/gridengine-master restart
	
	Then check the process again
		
		ps aux | grep sge 
	
	Make sure those two processes are up and running. 

* On Compute node do:

		apt-get isntall gridengine-client gridengine-exec
	
	An communication error similar to the one above might be thrown again. Thus, gridengine-exec fails to start. This time we will need to manually modify act_qmaster file, so the compute node knows which the master node is.
	
		echo ajen01.c.qtrinhcloud.internal > /var/lib/gridengine/default/common/act_qmaster
	
		 ** Replace "ajen01.c.qtrinhcloud.internal" with the master node. 
	Then,
	
		/etc/init.d/gridengine_exec start
	
	If you use qhost on Compute node, it will prompt error messages saying "ajen02" (my Compute node) is not in the access list. This is the indication that the internal communication has been successfully established.
	
	Right now we just need to go back to Master node to configure access list, users, groups, and etc. 

* Configure Master node: 

		sudo su
		sudo -u sgeadmin qconf -am FJen #FJen is my local user: the account I ssh to google cloud.
		exit
		qconf -au FJen users
		qconf -as ajen01
		qconf -ahgrp @allhosts  # just save the file without modifying it
		qconf -aattr hostgroup hostlist ajen01 @allhosts
		qconf -aq main.q # just save the file without modifying it
		qconf -aattr queue hostlist @allhosts main.q
		qconf -aattr queue slots "4, [ajen01=3]" main.q  # 4 by default for all nodes, 3 specifically for ajen01, which leaves 1 of the 4 cpus free for the master process

* Configure Compute node:

	

Useful Links
-----------------

**SGE on ubuntu:** 
	
	http://helms-deep.cable.nu/~rwh/blog/?p=159

*Laanguage package:** 
	
	http://forum.slicehost.com/index.php?p=/discussion/5065/error-in-locale/p1

**Star cluster:** 
	
	http://star.mit.edu/cluster/docs/0.92rc2/guides/sge.html


