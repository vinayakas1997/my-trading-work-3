"""Backward-compat entry point — delegates to vinu-initial-analysis."""
from vinu_initial_analysis.server.app import create_app

app = create_app()
