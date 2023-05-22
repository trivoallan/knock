#!/bin/sh

. /etc/os-release

if [ $ID = "debian"  ] && [ $VERSION_CODENAME = "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/debian bullseye main non-free contrib
deb http://repos.it.sncf.fr/debian bullseye-updates main non-free contrib
deb http://repos.it.sncf.fr/debian-security bullseye-security main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

if [ $ID = "debian"  ] && [ $VERSION_CODENAME != "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/debian ${VERSION_CODENAME} main non-free contrib
deb http://repos.it.sncf.fr/debian ${VERSION_CODENAME}-updates main non-free contrib
deb http://repos.it.sncf.fr/debian-security ${VERSION_CODENAME}/updates main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi
fi

if [ $ID = "ubuntu" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
EOF
fi