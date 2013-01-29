#start script for google cloud

#Update source.list
apt-get update

#Install language package
apt-get install language-pack-en-base
/usr/sbin/locale-gen en_IN.UTF-8
/usr/sbin/update-locale LANG=en_IN.UTF-8


