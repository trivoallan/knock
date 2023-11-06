#!/bin/sh

CACERTS_PATH=$(find /usr /opt -name cacerts | grep $JAVA_HOME)
DEBIAN=$(find /usr/local/share/ca-certificates/ -name ca-racine-sncf.crt || true)
CENTOS=$(find /etc/pki/ca-trust/source/anchors/ -name ca-racine-sncf.crt || true)

if [ ! -z "$CACERTS_PATH" ]
then
    if [ ! -z "$DEBIAN" ]
    then
        yes y | keytool -importcert -alias AC_RACINE_SNCF_2023 -keystore $CACERTS_PATH -storepass changeit -file /usr/local/share/ca-certificates/AC_RACINE_SNCF_2023.crt || true
        yes y | keytool -importcert -alias AC_INFRASTRUCTURE_SNCF_2023 -keystore $CACERTS_PATH -storepass changeit -file /usr/local/share/ca-certificates/AC_INFRASTRUCTURE_SNCF_2023.crt || true
        yes y | keytool -importcert -alias AC_RACINE_SNCF -keystore $CACERTS_PATH -storepass changeit -file /usr/local/share/ca-certificates/ca-racine-sncf.crt || true
        yes y | keytool -importcert -alias AC_INFRASTRUCTURE_SNCF -keystore $CACERTS_PATH -storepass changeit -file /usr/local/share/ca-certificates/AC_INFRASTRUCTURE_SNCF.crt || true
    fi
    if [ ! -z "$CENTOS" ]
    then
        yes y | keytool -importcert -alias AC_RACINE_SNCF -keystore $CACERTS_PATH -storepass changeit -file /etc/pki/ca-trust/source/anchors/ca-racine-sncf.crt || true
        yes y | keytool -importcert -alias AC_RACINE_SNCF_2023 -keystore $CACERTS_PATH -storepass changeit -file /etc/pki/ca-trust/source/anchors/AC_RACINE_SNCF_2023.crt || true
        yes y | keytool -importcert -alias AC_INFRASTRUCTURE_SNCF_2023 -keystore $CACERTS_PATH -storepass changeit -file /etc/pki/ca-trust/source/anchors/AC_INFRASTRUCTURE_SNCF_2023.crt || true
    fi
fi