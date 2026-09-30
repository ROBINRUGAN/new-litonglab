#!/bin/sh
# designed by mew
# Run as root. The environment file is root-owned and must use shell-safe KEY=value lines.
set -eu
set -a
. /etc/litonglab.env
set +a
cd /srv/litonglab/current
exec runuser -u litonglab -- .venv/bin/python backend/manage.py "$@"
