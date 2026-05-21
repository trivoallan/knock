#!/bin/sh

# Quitte au premier échec
set -e

# Chargement des infos de l'OS
. /etc/os-release

# Récupération de l'architecture
ARCH=$(uname -m)

# Installation de curl si nécessaire
if [ "$ID" = "debian" ] || [ "$ID" = "ubuntu" ]; then
    apt-get update
    apt-get install -y curl
fi

# Logique de téléchargement du keyring
# https://jira.apps.eul.sncf.fr/browse/TTC-8915?focusedId=3109746&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-3109746
if [ "$ARCH" = "x86_64" ]; then
    
    if [ "$ID" = "debian" ]; then
        curl -s https://repos.it.sncf.fr/os/debian/mirror/deb.debian.org/debian/pool/main/d/debian-keyring/debian-keyring_2021.07.26_all.deb --output /tmp/keyring.deb
    
    elif [ "$ID" = "ubuntu" ]; then
        curl -s "https://repos.it.sncf.fr/os/ubuntu/extra/pool/${VERSION_ID}/main/xsou/ubuntu-extra-keyring-sncf_1-1ubuntu${VERSION_ID}_amd64.deb" --output /tmp/keyring.deb
    fi

fi