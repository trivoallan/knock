#!/bin/sh

# Arrêt immédiat en cas de variable non définie
set -u

# --- DÉTECTION D'ARCHITECTURE ---
ARCH_RAW=$(uname -m)

# Normalisation pour l'usage interne
case "$ARCH_RAW" in
    x86_64)
        IS_ARM=0
        CENTOS_ARCH="x86_64"
        ;;
    aarch64|arm64)
        IS_ARM=1
        CENTOS_ARCH="aarch64"
        ;;
    *)
        echo "Attention: Architecture '$ARCH_RAW' non reconnue. Fallback sur x86_64."
        IS_ARM=0
        CENTOS_ARCH="x86_64"
        ;;
esac

echo "Architecture système détectée : $ARCH_RAW"

# Chargement des infos OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    echo "Erreur: /etc/os-release introuvable."
    exit 1
fi

# Variable de l'hôte
REPO_HOSTNAME="repos.it.sncf.fr"

echo "Configuration pour l'OS : $ID"

# --- ALPINE LINUX ---
if [ "$ID" = "alpine" ]; then
    ALPINE_MAJOR_MINOR=$(echo "$VERSION_ID" | cut -d '.' -f 1,2)
    echo " -> Configuration Alpine v$ALPINE_MAJOR_MINOR"
    
    cat <<EOF > /etc/apk/repositories
https://$REPO_HOSTNAME/os/alpine/prod.rsync.alpinelinux.org/v$ALPINE_MAJOR_MINOR/main
https://$REPO_HOSTNAME/os/alpine/prod.rsync.alpinelinux.org/v$ALPINE_MAJOR_MINOR/community
EOF
fi

# --- DEBIAN ---
if [ "$ID" = "debian" ]; then
    CODENAME=${VERSION_CODENAME:-$(echo "$VERSION" | sed 's/.*(\(.*\)).*/\1/')}
    echo " -> Configuration Debian ($CODENAME)"

    if [ "$CODENAME" = "buster" ]; then
        SEC_SUITE="buster/updates"
    else
        SEC_SUITE="$CODENAME-security"
    fi

    # Note: Debian gère généralement multi-arch sur le même miroir.
    # Si Debian ARM est aussi séparé, il faudra appliquer une logique similaire à Ubuntu.
    cat <<EOF > /etc/apt/sources.list
deb https://$REPO_HOSTNAME/debian $CODENAME main non-free contrib
deb https://$REPO_HOSTNAME/debian $CODENAME-updates main non-free contrib
deb https://$REPO_HOSTNAME/debian-security $SEC_SUITE main non-free contrib
EOF

    echo 'Acquire::Check-Valid-Until no;' > /etc/apt/apt.conf.d/99always-valid
fi

# --- UBUNTU ---
if [ "$ID" = "ubuntu" ]; then
    CODENAME=$VERSION_CODENAME
    echo " -> Configuration Ubuntu ($CODENAME) pour arch $ARCH_RAW"

    # Logique de bascule entre 'ubuntu' et 'ubuntu-ports'
    if [ "$IS_ARM" -eq 1 ]; then
        # Configuration ARM64
        REPO_BASE="ubuntu-ports"
        REPO_UPDATES="ubuntu-ports-updates"
        REPO_SECURITY="ubuntu-ports-security"
    else
        # Configuration AMD64 (x86_64)
        REPO_BASE="ubuntu"
        REPO_UPDATES="ubuntu-updates"
        REPO_SECURITY="ubuntu-security"
    fi
    
    cat <<EOF > /etc/apt/sources.list
deb https://$REPO_HOSTNAME/$REPO_BASE $CODENAME main restricted universe multiverse
deb https://$REPO_HOSTNAME/$REPO_UPDATES $CODENAME-updates main restricted universe multiverse
deb https://$REPO_HOSTNAME/$REPO_SECURITY $CODENAME-security main restricted universe multiverse
EOF
fi

# --- CENTOS ---
if [ "$ID" = "centos" ]; then
    echo " -> Configuration CentOS $VERSION_ID ($CENTOS_ARCH)"
    
    # Backup de sécurité
    if [ -d /etc/yum.repos.d ]; then
        mkdir -p /etc/yum.repos.d/backup_old_repos
        mv /etc/yum.repos.d/*.repo /etc/yum.repos.d/backup_old_repos/ 2>/dev/null || true
    fi

    if [ "$VERSION_ID" = "7" ]; then
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_7_Updates]
name=CentOS_7_Updates
baseurl=https://$REPO_HOSTNAME/repos/os/centos/Updates_yumcron/7/$CENTOS_ARCH
gpgcheck=0

[CentOS_7_Last]
name=CentOS_7_Last
baseurl=https://$REPO_HOSTNAME/repos/os/centos/7.last/$CENTOS_ARCH
gpgkey=https://$REPO_HOSTNAME/repos/os/centos/7.last/$CENTOS_ARCH/RPM-GPG-KEY-CentOS-7
EOF
    fi

    if [ "$VERSION_ID" = "8" ]; then
        cat <<EOF > /etc/yum.repos.d/sncf.repo
[CentOS_8_Updates_Security]
name=CentOS_8_Updates_Security
baseurl=https://$REPO_HOSTNAME/repos/os/centos/8.last/$CENTOS_ARCH/Updates/Security
gpgcheck=0

[CentOS_8_Updates_BaseOS]
name=CentOS_8_Updates_BaseOS
baseurl=https://$REPO_HOSTNAME/repos/os/centos/8.last/$CENTOS_ARCH/Updates/BaseOS
gpgcheck=0

[CentOS_8_Updates_AppStream]
name=CentOS_8_Updates_AppStream
baseurl=https://$REPO_HOSTNAME/repos/os/centos/8.last/$CENTOS_ARCH/Updates/AppStream
gpgcheck=0
EOF
    fi
fi