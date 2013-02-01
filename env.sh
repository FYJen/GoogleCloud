
DIR=`readlink -f .`
GCUTIL_HOME="$DIR/tools/gcutil"
export PATH=$GCUTIL_HOME/gcutil-1.5.0:${PATH}

GSUTIL_HOME="$DIR/tools/gsutil"
export PATH=$GSUTIL_HOME/gsutil:${PATH}
