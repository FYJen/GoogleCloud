
eval `ssh-agent`
ssh-add ~/.ssh/google_compute_engine


DIR=`pwd`
GCUTIL_HOME="$DIR/tools/gcutil"
export PATH=$GCUTIL_HOME/current:${PATH}

GSUTIL_HOME="$DIR/tools/gsutil"
export PATH=$GSUTIL_HOME/current:${PATH}

export PATH=${DIR}/bin:${PATH}



# The following credentials are prepared for MagFS:

export GC_ACCESS_KEY=YOUR_GOOGLE_ACCESS_KEY
export GC_SECRET_KEY=YOUR_GOOGLE_SECRET_KEY
# Below can be a random name (all lower cases)
export GC_CONTAINER=PICK_A_NAME
