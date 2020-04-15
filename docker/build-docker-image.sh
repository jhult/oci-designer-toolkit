#!/bin/bash

# Copyright (c) 2020, Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl.

source $(dirname $0)/docker-env.sh

docker images

docker rmi ${DOCKERIMAGE}

docker images

echo "*******************************************************************"
echo "**                                                               **"
echo "**  Building OL7 Image                                           **"
echo "**                                                               **"
echo "*******************************************************************"

#   --build-arg os_version="7-slim" \
docker build \
   --tag ${DOCKERIMAGE} \
   --file ${DOCKERDIR}/docker/Dockerfile \
   --force-rm \
   --build-arg http_proxy="${http_proxy}" \
   --build-arg https_proxy="${https_proxy}" \
   ${DOCKERDIR}/docker/

for dangling in $(docker images -f "dangling=true" -q)
do
    docker rmi ${dangling}
done

docker images


echo "*******************************************************************"
echo "**                                                               **"
echo "**  Image Build Complete                                         **"
echo "**  ${DOCKERIMAGE}                                               "
echo "**                                                               **"
echo "*******************************************************************"
