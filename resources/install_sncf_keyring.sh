#!/bin/sh

. /etc/os-release

if [ $ID = "debian" ] || [ $ID = "ubuntu" ]
then
    dpkg -i /tmp/keyring/keyring.deb
fi