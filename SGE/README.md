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

	.google_create.sh ajen00
	.google_create.sh ajen01

**Step 4:** Install prerequisites for SGE

switch to admin user
	
	sudo su

Update source.list
	
	apt-get update 

Install language package (optional; however, it is a bit messy when we are insatlling packages becasue some warrning messages will get thrown.)

	apt-get install language-pack-en-base
	/usr/sbin/locale-gen en_IN.UTF-8
	/usr/sbin/update-locale LANG=en_IN.UTF-8



Useful Links
-----------------

**SGE on ubuntu:** 
	
	http://helms-deep.cable.nu/~rwh/blog/?p=159

*Laanguage package:** 
	
	http://forum.slicehost.com/index.php?p=/discussion/5065/error-in-locale/p1

**Star cluster:** 
	
	http://star.mit.edu/cluster/docs/0.92rc2/guides/sge.html


