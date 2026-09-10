#!/bin/bash
# Docker building image test

set -e

IMAGE_NAME=${1:-rmit-store-frontend}
IMAGE_TAG=${2:-latest}

echo "Testing Docker build"


echo "Building docker image"
if docker build -t ${IMAGE_NAME}:${IMAGE_TAG} . ; then
    echo "Building image succeeded"
else
    echo "Building image failed"
    exit 1
fi


echo "Checking if image exist"
if docker images ${IMAGE_NAME}:${IMAGE_TAG} | grep -q ${IMAGE_NAME}; then
    echo "Image exists in local registry"
else
    echo "Image not found"
    exit 1
fi

echo "Building test passed"