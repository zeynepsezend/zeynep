import json
d = json.load(open(r'team_05\team_05_edited_layout.json', encoding='utf-8'))
rooms = d.get('rooms', [])
print(f'Total rooms: {len(rooms)}')
print()
for r in rooms:
    print(f"  {r['name']:18s} rate={r.get('rate_per_m2'):>6}  area={r.get('area_m2'):>6}  total={r.get('total_cost'):>10}")
print()
print('summary:', d.get('summary'))
