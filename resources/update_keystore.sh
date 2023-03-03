#!/bin/sh

CACERTS_PATH=$(find /usr /opt -name cacerts | grep $JAVA_HOME)

if [ ! -z "$CACERTS_PATH"  ]
then
    yes y | keytool -importcert -keystore $CACERTS_PATH -storepass changeit -file /usr/local/share/ca-certificates/ca-racine-sncf.crt
fi