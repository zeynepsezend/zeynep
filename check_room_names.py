import json
from pathlib import Path

layout_path = Path('team_05/gh/layout_schema-team05.json')
layout_data = json.loads(layout_path.read_text())

print('Room names in layout:')
for room in layout_data.get('rooms', []):
    name = room.get('name')
    area = room.get('area_m2')
    rate = room.get('rate_per_m2')
    cost = room.get('total_cost')
    print(f"  {repr(name):20} | Area: {area:5.2f} | Rate: {rate:5.0f} | Cost: {cost:8.0f}")
