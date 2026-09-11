#!/bin/bash
set -e

vinu-screener scan &
exec vinu-screener serve --host 0.0.0.0 --port 8095
