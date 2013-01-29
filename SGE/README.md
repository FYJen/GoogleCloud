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
		gcutil addinstance --image=projects/google/images/ubuntu-10-04-v20120912 ajen01 --wait_until_running --machine_type=n1-standard-4-d --zone=us-east1-a

Useful Links
-----------------

**SGE on ubuntu:** 
	
	http://helms-deep.cable.nu/~rwh/blog/?p=159

*Laanguage package:** 
	
	http://forum.slicehost.com/index.php?p=/discussion/5065/error-in-locale/p1

**Star cluster:** 
	
	http://star.mit.edu/cluster/docs/0.92rc2/guides/sge.html


