GoogleCloud
===========

This README file contains a quick reference for getting started with Google Cloud.

Documentations
=====================
General Google Compute Engine docs: https://developers.google.com/compute/docs/

Google Compute Engine tool ( gcutil ): https://developers.google.com/compute/docs/gcutil/

Google Cloud Storage tool ( gsutil ): https://developers.google.com/storage/docs/gsutil

Quick Getting Started with Google Cloud
=======================================

In your home directory, create a directory called 'GoogleCloud'.  Then download and install the latest gcutil and gsutil tools 

    mkdir ~/GoogleCloud
    
    cd ~/GoogleCloud ; mkdir gsutil ; cd gsutil ;  wget http://commondatastorage.googleapis.com/pub/gsutil.tar.gz
    tar xvf gsutil.tar.gz
    
    cd ~/GoogleCloud ; mkdir gcutil ; cd gcutil ; wget --no-check-certificate https://google-compute-engine-tools.googlecode.com/files/gcutil-1.5.0.tar.gz
    tar xvf gcutil-1.5.0.tar.gz
    
Add both gcutil and gsutil to your PATH

    GCUTIL_HOME="$HOME/GoogleCloud/gcutil"
    export PATH=${PATH}:$GCUTIL_HOME/gcutil-1.5.0

    GSUTIL_HOME="$HOME/GoogleCloud/gsutil"
    export PATH=${PATH}:$GSUTIL_HOME/gsutil


Set your environment variable PID to your Google Cloud project ID.  Run 'gcutil auth' to request a token. This command prints a URL where you can acquire an OAuth 2.0 refresh token for Google Compute Engine.

    PID="YOUR_GOOGLE_CLOUD_PROJECT_ID"
    gcutil auth --project_id=$PID
    
Set your default project

    gcutil getproject --project=$PID --cache_flag_values

Create a machine instance named 'i001' in zone 'us-east1-a' with machine instance type 'n1-standard-1'

    MACHINE_TYPE="n1-standard-1"; ZONE="us-east1-a"; gcutil addinstance i001 --wait_until_running --machine_type=$MACHINE_TYPE --zone=$ZONE
    
Login to your instance 'i001'

    gcutil ssh i001
    
    

