#!/bin/sh

. /etc/os-release

if [ $ID = "debian" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/os/debian/mirror/deb.debian.org/debian ${VERSION_CODENAME} main
deb-src http://repos.it.sncf.fr/os/debian/mirror/deb.debian.org/debian ${VERSION_CODENAME} main
EOF
fi

if [ $ID = "ubuntu" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse
deb-src http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse

deb http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse
deb-src http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse

deb http://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
deb-src http://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
EOF
fi