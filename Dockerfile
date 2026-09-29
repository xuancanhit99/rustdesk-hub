ARG RUSTDESK_UPSTREAM_IMAGE=rustdesk/rustdesk-server:1.1.16@sha256:8ecdab65deb7c84652a626380e31d11a8f1fbafd97916d57f95c20628f943c00
FROM ${RUSTDESK_UPSTREAM_IMAGE} AS rustdesk-upstream

FROM alpine:3.22.1@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1

RUN apk add --no-cache ca-certificates libgcc netcat-openbsd su-exec \
    && addgroup -g 10001 -S rustdesk \
    && adduser -u 10001 -S -D -H -G rustdesk rustdesk

COPY --from=rustdesk-upstream /usr/bin/hbbs /usr/local/bin/hbbs
COPY --from=rustdesk-upstream /usr/bin/hbbr /usr/local/bin/hbbr
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod 0755 /usr/local/bin/hbbs /usr/local/bin/hbbr /usr/local/bin/docker-entrypoint.sh

WORKDIR /data
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
STOPSIGNAL SIGTERM

LABEL org.opencontainers.image.title="RustDesk Hub runtime" \
      org.opencontainers.image.description="Hardened wrapper around the official RustDesk Server OSS binaries" \
      org.opencontainers.image.source="https://github.com/rustdesk/rustdesk-server" \
      org.opencontainers.image.licenses="AGPL-3.0"
