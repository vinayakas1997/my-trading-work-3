#!/bin/bash
set -e

vinu-initial-compute --all --continuous &
exec vinu-initial-serve --host 0.0.0.0 --port 8083
