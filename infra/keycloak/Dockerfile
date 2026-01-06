FROM quay.io/keycloak/keycloak:24.0

USER root
RUN microdnf update -y \
    && microdnf install -y curl \
    && microdnf clean all

USER 1000
