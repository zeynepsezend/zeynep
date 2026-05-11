import json
from pathlib import Path
from team_05.python._runtime.config import load_settings
from team_05.python._runtime.mcp_client import McpClient

settings = load_settings()
client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
client.initialize()

layout_path = Path('team_05/gh/layout_schema-team05.json')
layout_data = json.loads(layout_path.read_text())
layout_json = json.dumps(layout_data)

result = client.call_tool('compute_room_cost', {
    'room_name': 'Bathroom',
    'layout_schema': layout_json
})

# Check result structure
result_data = json.loads(result)
print('Result keys:', list(result_data.keys()))
print('Number of rooms:', len(result_data.get('rooms', [])))
if result_data.get('rooms'):
    print('First room name:', result_data['rooms'][0].get('name'))
    
    # Find Bathroom
    for room in result_data.get('rooms', []):
        if room.get('name') == 'Bathroom':
            print(f"\nBathroom Found:")
            print(f"  Area: {room.get('area_m2')} m²")
            print(f"  Rate: {room.get('rate_per_m2')} AED/m²")
            print(f"  Total Cost: {room.get('total_cost')} AED")
