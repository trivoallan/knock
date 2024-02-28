#!/bin/sh

. /etc/os-release

if [ "$ID" = "alpine" ]
then
    ALPINE_VERSION=$(cat /etc/alpine-release | cut -d '.' -f 1,2)
    cat <<EOF > /etc/apk/repositories
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v$ALPINE_VERSION/main
http://repos.it.sncf.fr/os/alpine/prod.rsync.alpinelinux.org/v$ALPINE_VERSION/community
EOF
fi

if [ "$ID" = "debian"  ] && [ "$(echo \"$VERSION\" | grep -oP '\(\K[^)]+')" = "buster" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/debian buster main non-free contrib
deb http://repos.it.sncf.fr/debian buster-updates main non-free contrib
deb http://repos.it.sncf.fr/debian-security buster/updates main non-free contrib
EOF
fi

if [ "$ID" = "debian"  ] && [ "$(echo \"$VERSION\" | grep -oP '\(\K[^)]+')" != "buster" ]
then
    cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/debian $(echo \"$VERSION\" | grep -oP '\(\K[^)]+') main non-free contrib
deb http://repos.it.sncf.fr/debian $(echo \"$VERSION\" | grep -oP '\(\K[^)]+')-updates main non-free contrib
deb http://repos.it.sncf.fr/debian-security $(echo \"$VERSION\" | grep -oP '\(\K[^)]+')-security main non-free contrib
EOF
fi

if [ "$ID" = "ubuntu" ]
then
    if [[ ${VERSION_ID:0:2} -ge 22 ]]
    then
        cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/ubuntu $VERSION_CODENAME main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu-updates $VERSION_CODENAME-updates main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu-security $VERSION_CODENAME-security main restricted universe multiverse
EOF
    else
        cat <<EOF > /etc/apt/sources.list
deb http://repos.it.sncf.fr/ubuntu $VERSION_CODENAME main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu $VERSION_CODENAME-updates main restricted universe multiverse
deb http://repos.it.sncf.fr/ubuntu-security $VERSION_CODENAME-security main restricted universe multiverse
EOF
    fi
fi