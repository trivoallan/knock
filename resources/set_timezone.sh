#!/bin/sh

. /etc/os-release

if [ "$ID" = "alpine" ]
then
    apk add --no-cache tzdata
else
    apt-get update
    export DEBIAN_FRONTEND=noninteractive && apt-get install -yq tzdata
    ln -fs /usr/share/zoneinfo/Europe/Paris /etc/localtime
    dpkg-reconfigure -f noninteractive tzdata
    rm -rf /var/lib/apt/lists/*
fi