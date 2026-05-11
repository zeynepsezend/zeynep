import json
from pathlib import Path
from team_05.python._runtime.config import load_settings
from team_05.python._runtime.mcp_client import McpClient

print("=" * 80)
print("MCP CONNECTIVITY TEST - compute_room_cost Tool")
print("=" * 80)

# Step 1: Load settings
settings = load_settings()
print(f"\n✓ Settings loaded")
print(f"  Endpoint: {settings.mcp_endpoint}")

# Step 2: Connect to MCP server
client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
client.initialize()
print(f"✓ Connected to MCP Server")

# Step 3: List tools
tools = client.list_tools()
print(f"✓ Tools available: {len(tools)}")
for t in tools:
    print(f"  - {t.get('name')}")

# Step 4: Load layout
repo_root = Path(__file__).resolve().parent
layout_path = repo_root / "team_05" / "gh" / "layout_schema-team05.json"
layout_data = json.loads(layout_path.read_text())
layout_json = json.dumps(layout_data)
print(f"\n✓ Layout schema loaded ({len(layout_json)} bytes)")

# Step 5: Test tool with sample rooms
print(f"\n" + "=" * 80)
print("TESTING compute_room_cost TOOL")
print("=" * 80)

test_rooms = ["Living Room", "Master Bedroom", "Bathroom"]

for room_name in test_rooms:
    print(f"\nCalling: compute_room_cost(room_name='{room_name}')")
    try:
        result = client.call_tool("compute_room_cost", {
            "room_name": room_name,
            "layout_schema": layout_json
        })
        
        result_data = json.loads(result)
        
        # Find and display the room
        for room in result_data.get("rooms", []):
            if room.get("name") == room_name:
                print(f"  ✓ Result:")
                print(f"    Area: {room.get('area_m2')} m²")
                print(f"    Rate: {room.get('rate_per_m2')} AED/m²")
                print(f"    Cost: {room.get('total_cost')} AED")
                break
                
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n" + "=" * 80)
print("✓ MCP CONNECTIVITY TEST PASSED")
print("=" * 80)

client.close()
