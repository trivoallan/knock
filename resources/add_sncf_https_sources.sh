#!/bin/sh

. /etc/os-release

if [ "$ID" = "alpine" ]
then
    ALPINE_VERSION=$(cat /etc/alpine-release | cut -d '.' -f 1,2)
    cat <<EOF > /etc/apk/repositories
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v${ALPINE_VERSION}/main
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v${ALPINE_VERSION}/community
EOF
fi

if [ "$ID" = "debian"  ] && [ "$VERSION_CODENAME" = "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/debian bullseye main non-free contrib
deb https://repos.it.sncf.fr/debian bullseye-updates main non-free contrib
deb https://repos.it.sncf.fr/debian-security bullseye-security main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

if [ "$ID" = "debian"  ] && [ "$VERSION_CODENAME" != "bullseye" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/debian ${VERSION_CODENAME} main non-free contrib
deb https://repos.it.sncf.fr/debian ${VERSION_CODENAME}-updates main non-free contrib
deb https://repos.it.sncf.fr/debian-security ${VERSION_CODENAME}/updates main non-free contrib
EOF
    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

if [ "$ID" = "ubuntu" ]
then
    cat <<EOF > /etc/apt/sources.list
deb https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME} main restricted universe multiverse
deb https://repos.it.sncf.fr/ubuntu ${VERSION_CODENAME}-updates main restricted universe multiverse
deb https://repos.it.sncf.fr/ubuntu-security ${VERSION_CODENAME}-security main restricted universe multiverse
EOF
fi

if [ "$ID" = "centos" ]
then
    if [ "$VERSION_ID" = "7" ]
    then
        rm -rf /etc/yum.repos.d/*
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_7_Updates]
name=CentOS_7_Updates
baseurl=https://repos.it.sncf.fr/repos/os/centos/Updates_yumcron/7/x86_64
gpgcheck=0
sslcacert=/etc/ssl/certs/ca-certificates.crt

[CentOS_7_Last]
name=CentOS_7_Last
baseurl=https://repos.it.sncf.fr/repos/os/centos/7.last/x86_64
gpgkey=https://repos.it.sncf.fr/repos/os/centos/7.last/x86_64/RPM-GPG-KEY-CentOS-7
sslcacert=/etc/ssl/certs/ca-certificates.crt
EOF
    fi

    if [ "$VERSION_ID" = "8" ]
    then
        rm -rf /etc/yum.repos.d/*
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_8_Updates_Security]
name=CentOS_8_Updates_Security
baseurl=https://repos.it.sncf.fr/repos/os/centos/8.last/x86_64/Updates/Security
gpgcheck=0
sslcacert=/etc/ssl/certs/ca-certificates.crt

[CentOS_8_Updates_BaseOS]
name=CentOS_8_Updates_BaseOS
baseurl=https://repos.it.sncf.fr/repos/os/centos/8.last/x86_64/Updates/BaseOS
gpgcheck=0
sslcacert=/etc/ssl/certs/ca-certificates.crt

[CentOS_8_Updates_AppStream]
name=CentOS_8_Updates_AppStream
baseurl=https://repos.it.sncf.fr/repos/os/centos/8.last/x86_64/Updates/AppStream
gpgcheck=0
sslcacert=/etc/ssl/certs/ca-certificates.crt
EOF
    fi

fi