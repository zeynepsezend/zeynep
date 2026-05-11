import json
from team_05.python._runtime.config import load_settings
from team_05.python._runtime.mcp_client import McpClient

settings = load_settings()
client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
client.initialize()
tools = client.list_tools()
for t in tools:
    print(f"Name: {repr(t.get('name'))}")
    print(f"Description: {t.get('description')}")
    print("---")
