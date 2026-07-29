#!/bin/bash
set -e

vinu-tools worker --loop &
exec vinu-tools serve --host 0.0.0.0 --port 8082
