Getting Started with Google Cloud
=================================

In your home directory, clone this repository, which has both gcutil and gsutil: 

        cd 
        git clone https://github.com/qtrinh/GoogleCloud
      
    
Change into GoogleCloud directory and set environments by doing:

        cd GoogleCloud
        . env.sh

Set your environment variable PID to your Google Cloud project ID.  Run 'gcutil auth' to request a token. This command prints a URL where you can acquire an OAuth 2.0 refresh token for Google Compute Engine.

        PID="YOUR_GOOGLE_CLOUD_PROJECT_ID"
        gcutil auth --project_id=$PID
    
Set your default project

        gcutil getproject --project=$PID --cache_flag_values

Add firewall. To serve a web page from an instance, you need to create a firewall rule that permits incoming HTTP traffic on port 80.
        
        gcutil addfirewall http2 --description="Incoming http allowed." --allowed="tcp:http"

Create a machine instance named 'i001' in 'us-east1-a' zone with machine instance type 'n1-standard-1'

        gcutil addinstance i001 --wait_until_running --machine_type=n1-standard-1 --zone=us-east1-a
    
Login to your instance 'i001'

        gcutil ssh i001
    

Once you are done with your instance, terminate it

        gcutil deleteinstance i001


There are many other gcutil commands - please see the gcutil documentation at https://developers.google.com/compute/docs/gcutil/ 
