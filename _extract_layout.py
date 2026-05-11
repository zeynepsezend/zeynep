import re, json, sys, ast
p = r"c:\Users\merof\AppData\Roaming\Code\User\workspaceStorage\a70d7fa50205c69e148ed57584e7e6f3\GitHub.copilot-chat\chat-session-resources\e12aa496-a303-4423-8fbc-ce3506714b8b\toolu_vrtx_01CZiX1C7JdBCmE1t4ZnStms__vscode-1778469759684\content.txt"
t = open(p, encoding="utf-8", errors="replace").read()
# Find the printed dict args: arguments: {'room_name': ..., 'layout_schema': '...'}
m = re.search(r"with arguments:\s*(\{.*?\})\s*(?:\[ENFORCE\]|\n[A-Z])", t, re.S)
if not m:
    print("no arguments block found"); sys.exit()
args_repr = m.group(1)
try:
    args = ast.literal_eval(args_repr)
except Exception as e:
    print("ast.literal_eval failed:", e); sys.exit()
layout_str = args.get("layout_schema", "")
print(f"room_name = {args.get('room_name')!r}")
print(f"layout_schema length = {len(layout_str)} bytes\n")
try:
    obj = json.loads(layout_str)
    print(json.dumps(obj, indent=2)[:8000])
except Exception as e:
    print("json parse failed:", e)
    print(layout_str[:2000])
