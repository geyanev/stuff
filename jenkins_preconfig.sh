#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

curl -sSL https://get.docker.com/ | sh

zpool create jenkins mirror /dev/vdb /dev/vdc
zfs create jenkins/workspace
