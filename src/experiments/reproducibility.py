import sys
import platform
import importlib.metadata
from datetime import datetime, timezone

def environment():
    return dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),
                versions={p:importlib.metadata.version(p) for p in ['numpy','scipy','qiskit','qiskit-aer','networkx','streamlit','plotly']})
