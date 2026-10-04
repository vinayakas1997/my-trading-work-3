#!/bin/bash
set -e

# Two processes in one container: the read-only HTTP API (the agent reads the hourly synthesis and the notable beliefs
# from it) and the worker loop that writes them. Without the API every reflection read in the agent failed with
# "connection refused", so the learning brain never reached a decision.
vinu-reflection serve --host 0.0.0.0 --port "${VINU_REFLECTION_PORT:-8092}" &
exec vinu-reflection worker
