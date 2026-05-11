import json
from pathlib import Path
from team_05.python._runtime.config import load_settings
from team_05.python._runtime.mcp_client import McpClient

print("=" * 80)
print("MCP CONNECTIVITY TEST FOR compute_room_cost")
print("=" * 80)

# Load settings and connect
settings = load_settings()
print(f"\n✓ Settings loaded")
print(f"  MCP Endpoint: {settings.mcp_endpoint}")
print(f"  Request Timeout: {settings.request_timeout_seconds}s")

# Initialize MCP client
client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
client.initialize()
print(f"\n✓ MCP Server connected")

# List available tools
tools = client.list_tools()
print(f"\n✓ Tools discovered: {len(tools)}")
for t in tools:
    print(f"  - {t.get('name')}")

# Load layout schema
repo_root = Path(__file__).resolve().parent
layout_path = repo_root / "team_05" / "gh" / "layout_schema-team05.json"
layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
layout_json_string = json.dumps(layout_data)
print(f"\n✓ Layout schema loaded ({len(layout_json_string)} bytes)")

# Test compute_room_cost tool
print("\n" + "=" * 80)
print("TESTING compute_room_cost")
print("=" * 80)

test_room = "Living Room"
print(f"\nCalling compute_room_cost for: '{test_room}'")

try:
    result = client.call_tool("compute_room_cost", {
        "room_name": test_room,
        "layout_schema": layout_json_string
    })
    print(f"\n✓ Tool executed successfully!")
    print(f"\n✓ Parsing result...")
    
    try:
        result_json = json.loads(result)
        # Find the room in the result
        if "rooms" in result_json:
            for room in result_json["rooms"]:
                if room.get("name") == test_room:
                    print(f"\n✓ Room Cost Calculation:")
                    print(f"  Room: {room.get('name')}")
                    print(f"  Area: {room.get('area_m2')} m²")
                    print(f"  Rate: {room.get('rate_per_m2')} AED/m²")
                    print(f"  Total Cost: {room.get('total_cost')} AED")
                    print(f"  Category: {room.get('category')}")
                    break
        else:
            print("  Warning: No rooms found in result")
    except Exception as parse_err:
        print(f"  Error parsing result: {parse_err}")
        print(f"  Raw result (first 300 chars): {result[:300]}")
        
except Exception as e:
    print(f"\n✗ Error calling tool: {e}")
    import traceback
    traceback.print_exc()

# Test with another room
print("\n" + "-" * 80)
test_room2 = "Master Bedroom"
print(f"\nCalling compute_room_cost for: '{test_room2}'")

try:
    result2 = client.call_tool("compute_room_cost", {
        "room_name": test_room2,
        "layout_schema": layout_json_string
    })
    print(f"\n✓ Tool executed successfully!")
    print(f"\n✓ Parsing result...")
    
    try:
        result_json = json.loads(result2)
        if "rooms" in result_json:
            for room in result_json["rooms"]:
                if room.get("name") == test_room2:
                    print(f"\n✓ Room Cost Calculation:")
                    print(f"  Room: {room.get('name')}")
                    print(f"  Area: {room.get('area_m2')} m²")
                    print(f"  Rate: {room.get('rate_per_m2')} AED/m²")
                    print(f"  Total Cost: {room.get('total_cost')} AED")
                    print(f"  Category: {room.get('category')}")
                    break
        else:
            print("  Warning: No rooms found in result")
    except Exception as parse_err:
        print(f"  Error parsing result: {parse_err}")
        
except Exception as e:
    print(f"\n✗ Error calling tool: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

client.close()
