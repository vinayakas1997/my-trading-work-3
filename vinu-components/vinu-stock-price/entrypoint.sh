#!/bin/bash
set -e

vinu-stock-ingest --interval 60 &
exec vinu-stock-serve --host 0.0.0.0 --port 8081
