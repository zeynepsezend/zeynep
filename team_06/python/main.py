import argparse
from _runtime.bootstrap import bootstrap
from _runtime.session import load_session_state, save_session_state, clear_session
from graph import run_agent


def main():

    # Process the command line arguments (the user instruction)
    parser = argparse.ArgumentParser(description="Run the Grasshopper MCP agent.")
    parser.add_argument("prompt", help="Your instruction for the agent (e.g. 'delete the kitchen')")
    parser.add_argument("--clear-session", action="store_true", help="Clear session history and start fresh")
    args = parser.parse_args()

    # Load any previous session state (context from previous runs)
    if args.clear_session:
        clear_session()
        session_state = None
    else:
        session_state = load_session_state()
    
    if session_state:
        print(f"[main] Resuming session with {len(session_state.get('messages', []))} previous messages")
    else:
        print("[main] Starting fresh session")

    # Initialize and run the agent
    ctx = bootstrap()
    response, final_state = run_agent(args.prompt, ctx, session_state)

    # Print the final response
    print("\nAgent response:\n")
    safe_response = response.encode("ascii", errors="replace").decode("ascii")
    print(safe_response)

    # Save the session state for the next run
    save_session_state(final_state)

    # Clean up by properly closing the MCP client connection
    ctx.mcp_client.close()


if __name__ == "__main__":
    main()
