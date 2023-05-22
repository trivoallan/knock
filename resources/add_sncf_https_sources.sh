#!/bin/sh

. /etc/os-release

if [ $ID = "alpine" ]
then
    ALPINE_VERSION=$(cat /etc/alpine-release | cut -d '.' -f 1,2)
    cat <<EOF > /etc/apk/repositories
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v${ALPINE_VERSION}/main
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v${ALPINE_VERSION}/community
EOF
fi

if [ $ID = "debian"  ] && [ $VERSION_CODENAME = "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/debian bullseye main non-free contrib
deb https://repos.it.sncf.fr/debian bullseye-updates main non-free contrib
deb https://repos.it.sncf.fr/debian-security bullseye-security main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

if [ $ID = "debian"  ] && [ $VERSION_CODENAME != "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/debian ${VERSION_CODENAME} main non-free contrib
deb https://repos.it.sncf.fr/debian ${VERSION_CODENAME}-updates main non-free contrib
deb https://repos.it.sncf.fr/debian-security ${VERSION_CODENAME}/updates main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

if [ $ID = "ubuntu" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse
deb-src https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse

deb https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse
deb-src https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse

deb https://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
deb-src https://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
EOF
fi

if [ $ID = "centos" ]
then
    CENTOS_VERSION=$(cat /etc/centos-release | cut -d ' ' -f 4 | cut -d '.' -f 1,2)

    if [ $VERSION_ID = "7" ]
    then
        rm -rf /etc/yum.repos.d/*
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_${CENTOS_VERSION}]
name=CentOS_${CENTOS_VERSION}
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64
gpgkey=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/RPM-GPG-KEY-CentOS-7
https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/RPM-GPG-KEY-redhat-release
sslcacert=/etc/ssl/certs/ca-certificates.crt

[CentOS_${CENTOS_VERSION}_Security]
name=CentOS_${CENTOS_VERSION}_Security
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Security
gpgkey=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/RPM-GPG-KEY-CentOS-7
https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/RPM-GPG-KEY-redhat-release
sslcacert=/etc/ssl/certs/ca-certificates.crt

[CentOS_${CENTOS_VERSION}_Extra]
name=CentOS_${CENTOS_VERSION}_Extra
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Extra
gpgkey=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/RPM-GPG-KEY-unixsys
sslcacert=/etc/ssl/certs/ca-certificates.crt
EOF
    fi

    if [ $VERSION_ID = "8" ]
    then
        rm -rf /etc/yum.repos.d/*
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_${CENTOS_VERSION}_BaseOS]
name=CentOS_${CENTOS_VERSION}_BaseOS
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/BaseOS
gpgcheck=1
enabled=1[CentOS_${CENTOS_VERSION}_AppStream]
name=CentOS_${CENTOS_VERSION}_AppStream
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/AppStream
gpgcheck=1
enabled=1[CentOS_${CENTOS_VERSION}_Extra]
name=CentOS_${CENTOS_VERSION}_Extra
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Extra
gpgcheck=1
enabled=1

[CentOS_${CENTOS_VERSION}_Updates_Security]
name=CentOS_${CENTOS_VERSION}_Updates_Security
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Updates/Security
gpgcheck=1
enabled=0[CentOS_${CENTOS_VERSION}_Updates_BaseOS]
name=CentOS_${CENTOS_VERSION}_Updates_BaseOS
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Updates/BaseOS
gpgcheck=1
enabled=0[CentOS_${CENTOS_VERSION}_Updates_AppStream]
name=CentOS_${CENTOS_VERSION}_Updates_AppStream
baseurl=https://repos.it.sncf.fr/repos/os/centos/${CENTOS_VERSION}/x86_64/Updates/AppStream
gpgcheck=1
enabled=0
EOF
    fi

fi