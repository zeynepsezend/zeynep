"""
main.py - Sensi entry point.

The while loop here IS the idle state. The agent stays alive between turns,
carrying layout and persona across the conversation.

Commands:
  exit / quit / bye / goodbye  -> close and end the session
  reset                        -> clear the loaded layout and persona
  <anything>                   -> run one turn of the agent graph
"""

import re
from _runtime.bootstrap import bootstrap
from graph import run_agent


def _clean_response(text: str) -> str:
    """Strip markdown formatting and normalize unicode for terminal display."""
    # Remove bold/italic markdown
    text = re.sub(r'\*+(.*?)\*+', r'\1', text)
    text = re.sub(r'_+(.*?)_+', r'\1', text)
    # Replace common unicode punctuation with ASCII equivalents
    text = text.replace('—', ' - ')   # em dash
    text = text.replace('–', ' - ')   # en dash
    text = text.replace('’', "'")     # right single quote
    text = text.replace('‘', "'")     # left single quote
    text = text.replace('“', '"')     # left double quote
    text = text.replace('”', '"')     # right double quote
    text = text.replace('•', '-')     # bullet
    text = text.replace('é', 'e')     # e acute
    text = text.replace('è', 'e')     # e grave
    # Replace any remaining non-ASCII with ?
    return text.encode('ascii', errors='replace').decode('ascii')


_WELCOME = """
+------------------------------------------------------+
|                  hi, i'm sensi :)                    |
|  your sensorial comfort companion for apartment      |
|  layouts -- thermal, visual, acoustic, spatial,      |
|  olfactory, and tactile comfort, all in one place.   |
+------------------------------------------------------+
|  Type  reset  to start over.                         |
|  Type  exit   to quit.                               |
+------------------------------------------------------+
"""


def _print_session_status(session: dict) -> None:
    """Print a compact one-line summary of what is loaded in the session."""
    layout_id = session.get("layout_id")
    persona   = session.get("persona_profile")
    parts = []
    if layout_id:
        parts.append("layout {}".format(layout_id))
    if persona:
        parts.append("persona loaded")
    if parts:
        print("[session] {}".format(" | ".join(parts)))


def main() -> None:
    print(_WELCOME)

    # Bootstrap once - MCP connection stays open for the whole session
    ctx = bootstrap()

    # Session carries layout and persona across turns
    session: dict = {}

    # Auto-greet on first launch - run one silent turn so GREET fires first
    try:
        response, session = run_agent("", ctx, session)
        print("\nSensi:\n")
        print(_clean_response(response))
        print()
    except Exception as exc:
        print("\n[error] Could not start greeting: {}".format(exc))

    while True:

        _print_session_status(session)
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        # Commands
        if user_input.lower() in ("exit", "quit", "bye", "goodbye"):
            print("\nSensi:\n")
            print("Bye! Come back when you have a layout to explore :)")
            break

        if user_input.lower() == "reset":
            session = {}
            print("[session] Cleared -- layout and persona reset.")
            continue

        # Run one turn of the agent graph
        try:
            response, session = run_agent(user_input, ctx, session)
        except Exception as exc:
            print("\n[error] Something went wrong: {}".format(exc))
            print("The session is still active. Try again or type 'reset'.")
            continue

        print("\nSensi:\n")
        print(_clean_response(response))
        print()

    # Cleanup
    ctx.mcp_client.close()


if __name__ == "__main__":
    main()
