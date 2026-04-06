import argparse

from _runtime.bootstrap import bootstrap
from graph import run_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Grasshopper MCP agent.")
    parser.add_argument("prompt", help="Your instruction for the agent (e.g. 'delete the kitchen')")
    args = parser.parse_args()

    ctx = bootstrap()
    response = run_agent(args.prompt, ctx)

    print("\nAgent response:\n")
    safe_response = response.encode("ascii", errors="replace").decode("ascii")
    print(safe_response)

    ctx.mcp_client.close()


if __name__ == "__main__":
    main()
