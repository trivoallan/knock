#!/bin/sh

. /etc/os-release

if [ -f /tmp/keyring/keyring.deb ]; then
    if [ "$ID" = "debian" ] || [ "$ID" = "ubuntu" ]; then
        dpkg -i /tmp/keyring/keyring.deb
    fi
fi