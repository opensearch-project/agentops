ARG OPENSEARCH_VERSION
ARG OPENSEARCH_DOCKER_REPO

# Use OpenSearch image as base
FROM ${OPENSEARCH_DOCKER_REPO}/opensearch:${OPENSEARCH_VERSION}

# from https://github.com/opensearch-project/opensearch-build/blob/25740e9f9e1da93d8c600eff8dd20b613ebb94f0/docker/release/dockerfiles/opensearch.al2023.dockerfile
ENTRYPOINT ["./opensearch-docker-entrypoint.sh"]
CMD ["opensearch"]