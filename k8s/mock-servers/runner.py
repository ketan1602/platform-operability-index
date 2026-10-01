"""Start HTTP (FastAPI/uvicorn) + MCP (fastmcp) servers for a single mock service.

Controlled entirely by env vars:
  SERVER_MODULE  module name (e.g. mock_api_server)
  HTTP_PORT      uvicorn port  (default 8001)
  MCP_PORT       fastmcp port  (default 9001)
"""
from __future__ import annotations
import importlib
import os
import subprocess
import sys

import uvicorn

MODULE    = os.environ["SERVER_MODULE"]
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8001"))
MCP_PORT  = int(os.environ.get("MCP_PORT",  "9001"))

mcp_proc = subprocess.Popen(
    [sys.executable, "-c",
     f"import {MODULE} as m; m.mcp_app.run(transport='streamable-http', host='0.0.0.0', port={MCP_PORT})"],
)
try:
    mod = importlib.import_module(MODULE)
    uvicorn.run(mod.app, host="0.0.0.0", port=HTTP_PORT)
finally:
    mcp_proc.terminate()
    mcp_proc.wait()
