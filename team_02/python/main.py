import argparse
from pathlib import Path
from _runtime.bootstrap import bootstrap, select_layout
from graph import run_agent


def main():

    # Process the command line arguments (the user instruction)
    parser = argparse.ArgumentParser(description="Run the Grasshopper MCP agent.")
    parser.add_argument("prompt", help="Your instruction for the agent (e.g. 'delete the kitchen')")
    args = parser.parse_args()

    # Prompt the user to select a layout file
    repo_root = Path(__file__).resolve().parents[2]
    layout_path = select_layout(repo_root)

    # Initialize and run the agent with the selected layout
    ctx = bootstrap(layout_path=layout_path)
    response = run_agent(args.prompt, ctx)

    # Print the final response
    print("\nAgent response:\n")
    safe_response = response.encode("ascii", errors="replace").decode("ascii")
    print(safe_response)

    # Clean up by properly closing the MCP client connection
    ctx.mcp_client.close()


if __name__ == "__main__":
    main()
