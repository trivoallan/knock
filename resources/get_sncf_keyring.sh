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
    curl -s https://repos.it.sncf.fr/os/debian/mirror/deb.debian.org/debian/pool/main/d/debian-keyring/debian-keyring_2021.07.26_all.deb --output /tmp/keyring.deb
fi

if [ "$ID" = "ubuntu" ]
then
    curl -s https://repos.it.sncf.fr/os/ubuntu/extra/pool/${VERSION_ID}/main/xsou/ubuntu-extra-keyring-sncf_1-1ubuntu${VERSION_ID}_amd64.deb --output /tmp/keyring.deb
fi