FROM alpine:3.19

RUN apk add --no-cache curl ca-certificates

COPY --from=openpolicyagent/opa:0.62.1-static /opa /usr/local/bin/opa

ENTRYPOINT ["/usr/local/bin/opa"]
