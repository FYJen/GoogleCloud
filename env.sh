
eval `ssh-agent`
ssh-add ~/.ssh/google_compute_engine


DIR=`pwd`
GCUTIL_HOME="$DIR/tools/gcutil"
export PATH=$GCUTIL_HOME/current:${PATH}

GSUTIL_HOME="$DIR/tools/gsutil"
export PATH=$GSUTIL_HOME/current:${PATH}

export PATH=${DIR}/bin:${PATH}
