#!/bin/sh

# Exits on first error
set -e

. /etc/os-release

if [ "$ID" = "debian" ] || [ "$ID" = "ubuntu" ]
then
    apt-get update
    apt-get install -y curl
fi

if [ "$ID" = "debian" ]
then
    curl -s http://repos.it.sncf.fr/os/debian/mirror/deb.debian.org/debian/pool/main/d/debian-keyring/debian-keyring_2021.07.26_all.deb --output /tmp/keyring.deb
fi

if [ "$ID" = "ubuntu" ]
then
    if [ "$VERSION_CODENAME" = "jammy" ]
    then
        curl -s http://repos.it.sncf.fr/os/ubuntu/extra/pool/jammy/main/xsou/ubuntu-extra-keyring-sncf_1.0-1~ubuntu22.04_all.deb --output /tmp/keyring.deb
    else
        curl -s http://repos.it.sncf.fr/os/ubuntu/extra/pool/$VERSION_CODENAME/main/xsou/ubuntu-extra-keyring-sncf_1.0-1_all.deb --output /tmp/keyring.deb
    fi
fi