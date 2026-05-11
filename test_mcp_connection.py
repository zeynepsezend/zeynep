#!/usr/bin/env python3
"""
Quick MCP Connection Test
Tests connectivity to Grasshopper MCP server and verifies tool availability
"""
import sys
import json

# Import the MCP client
sys.path.insert(0, "team_05/python/_runtime")
from mcp_client import McpClient

def test_mcp_connection():
    """Test MCP connection and tool discovery"""
    
    print("=" * 70)
    print("MCP CONNECTION TEST")
    print("=" * 70)
    
    try:
        # Initialize MCP client
        print("\n[1] Initializing MCP client at http://localhost:3003/mcp/...")
        client = McpClient(endpoint="http://localhost:3003/mcp/", timeout_seconds=10)
        
        # Initialize connection
        print("[2] Initializing MCP connection...")
        client.initialize()
        print("✅ MCP connection established successfully!")
        
        # List available tools
        print("\n[3] Discovering available tools...")
        tools = client.list_tools()
        print(f"✅ Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"   {i}. {tool['name']} - {tool['description']}")
        
        # Test a simple tool call
        print("\n[4] Testing tool execution: compute_volume_of_cube...")
        result = client.call_tool("compute_volume_of_cube", {"side_length": 5})
        print(f"✅ Tool call successful!")
        print(f"   Input: side_length=5")
        print(f"   Output: {result}")
        
        # Parse and validate the response
        try:
            result_json = json.loads(result)
            if isinstance(result_json, dict) and "volume" in result_json:
                print(f"   Volume: {result_json['volume']} cubic units")
        except:
            pass
        
        # Test compute_room_cost with sample layout
        print("\n[5] Testing compute_room_cost tool...")
        
        # Load layout from file
        with open("team_05/gh/layout_schema-team05.json", "r") as f:
            layout_schema = json.load(f)
        
        layout_str = json.dumps(layout_schema)
        result = client.call_tool("compute_room_cost", {
            "room_name": "Living Room",
            "layout_schema": layout_str
        })
        print(f"✅ compute_room_cost call successful!")
        
        try:
            result_json = json.loads(result)
            if isinstance(result_json, dict) and "rooms" in result_json:
                for room in result_json.get("rooms", []):
                    if room.get("name") == "Living Room":
                        print(f"   Living Room: {room.get('area_m2')} m² @ {room.get('rate_per_m2')} AED/m² = {room.get('cost')} AED")
        except:
            print(f"   Response: {result[:200]}...")
        
        print("\n" + "=" * 70)
        print("✅ MCP CONNECTION TEST PASSED")
        print("=" * 70)
        print("\nAll tests completed successfully!")
        print("The MCP connection is working properly and tools are responding.")
        return True
        
    except Exception as e:
        print(f"\n❌ MCP CONNECTION TEST FAILED")
        print(f"Error: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Check that Swiftlet Bridge is running:")
        print("   Start-Process 'C:\\Users\\merof\\AppData\\Roaming\\McNeel\\Rhinoceros\\packages\\8.0\\swiftlet\\0.2.0\\SwiftletBridge.exe' -ArgumentList 'http://localhost:3003/mcp/'")
        print("2. Verify mcp.json has correct endpoint: http://localhost:3003/mcp/")
        print("3. Check that Grasshopper is open with team_05_working.gh loaded")
        print("4. Verify network connectivity to localhost:3003")
        return False

if __name__ == "__main__":
    success = test_mcp_connection()
    sys.exit(0 if success else 1)
