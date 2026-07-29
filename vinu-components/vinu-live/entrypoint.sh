#!/bin/bash
set -e

vinu-live-worker --interval 3600 &
exec vinu-live serve --host 0.0.0.0 --port 8091
