#!/bin/bash
set -e

vinu-research schedule-decay --interval-hours 24 &
exec vinu-research serve --host 0.0.0.0 --port 8087
