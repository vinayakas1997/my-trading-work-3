#!/bin/bash
set -e

vinu-portfolio monitor &
exec vinu-portfolio serve --host 0.0.0.0 --port 8090
