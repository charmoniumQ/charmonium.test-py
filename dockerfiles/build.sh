#!/usr/bin/env sh

set -e -x

if [ -z "${DOCKER_REGISTRY}" ]; then
	echo "Please define DOCKER_REGISTRY before running."
	exit 1
fi

if cat ~/.docker/config.json \
		| jq --exit-status '.auths | length | . == 0' > /dev/null; then
	echo "Please log in to ${DOCKER_REGISTRY}"
	echo "For Azure, this is 'az acr login --name ${DOCKER_REGISTRY}'"
	exit 1
fi

tag="$(./dockerfiles/tag.sh)"

nix build --show-trace --print-build-logs .#charmonium-test-py-image
image=$(docker load --input result | cut --fields=3 --delimiter=' ')
unlink result
docker tag "${image}" "${DOCKER_REGISTRY}/charmonium-test-py:${tag}"
docker push "${DOCKER_REGISTRY}/charmonium-test-py:${tag}"
echo "${DOCKER_REGISTRY}/charmonium-test-py:${tag}" > dockerfiles/charmonium_test_py_image

docker build dockerfiles/trisovic-runner --tag "${DOCKER_REGISTRY}/trisovic-runner:${tag}" --memory 10Gib
docker push "${DOCKER_REGISTRY}/trisovic-runner:${tag}"
echo "${DOCKER_REGISTRY}/trisovic-runner:${tag}" > dockerfiles/trisovic_runner_image
