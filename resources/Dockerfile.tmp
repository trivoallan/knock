FROM docker.io/{IMAGE}:{TAG}

USER root

# Alpine
COPY sources_http.list /etc/apk/repositories
COPY ca-racine-sncf.pem /usr/local/share/ca-certificates/ca-racine-sncf.crt
RUN apk update && apk add --no-cache ca-certificates && update-ca-certificates || true
COPY sources_https.list /etc/apk/repositories

# Ubuntu
COPY sources_http.list /etc/apt/sources.list
COPY ubuntu-extra-keyring-sncf.deb /temp/ubuntu-extra-keyring-sncf.deb
COPY ca-racine-sncf.pem /usr/local/share/ca-certificates/ca-racine-sncf.crt
COPY ca-racine-sncf.pem /etc/apt/certs/ca-racine-sncf.pem
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && update-ca-certificates && dpkg -i /temp/ubuntu-extra-keyring-sncf.deb || true; apt-get clean && apt-get autoclean && apt-get autoremove && rm -rf /var/lib/apt/lists/*
COPY sources_https.list /etc/apt/sources.list

# Debian
COPY sources_http.list /etc/apt/sources.list
COPY debian-keyring_2021.07.26_all.deb /temp/debian-keyring_2021.07.26_all.deb
COPY ca-racine-sncf.pem /usr/local/share/ca-certificates/ca-racine-sncf.crt
COPY ca-racine-sncf.pem /etc/apt/certs/ca-racine-sncf.pem
COPY 99always-valid /etc/apt/apt.conf.d/99always-valid
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && update-ca-certificates && dpkg -i /temp/debian-keyring_2021.07.26_all.deb || true; apt-get clean && apt-get autoclean && apt-get autoremove && rm -rf /var/lib/apt/lists/*
COPY sources_https.list /etc/apt/sources.list

# CentOS
RUN rm -f /etc/yum.repos.d/*.repo
COPY sources_http.list /etc/yum.repos.d/sncf.repo
COPY ca-racine-sncf.pem /etc/yum/certs/ca-racine-sncf.pem
RUN yum install -y ac-racine-SNCF.x86_64 || true && mkdir -p /usr/local/share/ca-certificates && cp -p /etc/yum/certs/ca-racine-sncf.pem /usr/local/share/ca-certificates/ca-racine-sncf.crt
COPY sources_https.list /etc/yum.conf

# if KEYSTORE
RUN yes y | keytool -importcert -keystore ${KEYSTORE} -storepass changeit -file /usr/local/share/ca-certificates/ca-racine-sncf.crt || true


COPY ca-racine-sncf.pem /usr/local/share/ca-certificates/ca-racine-sncf.crt

RUN apk update && apk add --no-cache ca-certificates && update-ca-certificates || true

LABEL fr.sncf.h2h.date_1ereDispo={CREATION_DATE}
LABEL fr.sncf.h2h.build-date={BUILD_DATE}
LABEL fr.sncf.h2h.version={HCR_TAG}
LABEL fr.sncf.h2h.version_editeur={ORIGIN_TAG}
LABEL fr.sncf.h2h.product={PRODUCT}
LABEL fr.sncf.h2h.maintainer={MAINTAINER}
LABEL fr.sncf.h2h.dockerfile={DOCKERFILE}
LABEL fr.sncf.h2h.urldockerhub={DOCKERHUB_URL}
LABEL fr.sncf.niv_exploit={EXPLOIT_LEVEL}
LABEL fr.sncf.source_type=h2h
LABEL fr.sncf.num_inc=
LABEL sha_ext_org={ORIGIN_DIGEST}
