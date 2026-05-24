"""
LangGraph Agent Orchestration Layer
Routes user input to Python Copilot or Swiftlet MCP tools.
After a finish-change request, stores an updated layout for the caller to use.
"""
import json

from python_copilot import apply_finish_to_layout, process_with_copilot
from swiftlet_mcp import process_with_swiftlet, push_layout_to_grasshopper


class LangGraphAgent:
    def __init__(self) -> None:
        self._updated_layout: dict | None = None

    def process(
        self,
        user_input: str,
        layout: dict | None = None,
        plans: dict[str, dict] | None = None,
        active_plan_key: str | None = None,
        history: list[dict] | None = None,
    ) -> str:
        """Route input to the appropriate backend and return the response text."""
        self._updated_layout = None  # reset on each call

        context = self._build_context(user_input, layout, plans, active_plan_key, history)

        if self._should_compare_plans(user_input, plans) and plans:
            response = self._compare_plans(user_input, plans, active_plan_key)
            return response

        if self._should_use_copilot(user_input):
            response = process_with_copilot(context)
            # if this was a finish-change, produce the updated layout and push to GH
            if layout is not None:
                updated = apply_finish_to_layout(user_input, layout)
                if updated is not None:
                    self._updated_layout = updated
                    self._push_to_grasshopper(user_input, updated)
        else:
            response = process_with_swiftlet(context)

        return response

    def get_updated_layout(self) -> dict | None:
        """
        Returns the layout with recalculated costs and colors after a finish change,
        or None if the last call did not modify the layout.
        """
        return self._updated_layout

    def _push_to_grasshopper(self, user_input: str, updated_layout: dict) -> None:
        """
        Push the updated layout to GH and adopt GH's returned layout as
        authoritative so the GUI floor plan shows the same colors as GH.
        GH returns the same room IDs as we sent, so id-based merge works.
        """
        try:
            from python_copilot import _find_room
            rooms = updated_layout.get("rooms", [])
            room = _find_room(user_input.lower(), rooms)
            room_name = room.get("name") if room else None
            result = push_layout_to_grasshopper(updated_layout, room_name)
            if result["ok"]:
                print(f"[GH] Layout pushed via {result['tool']} for room '{room_name}'")
                if result.get("gh_layout"):
                    self._updated_layout = result["gh_layout"]
                    print("[GH] Adopted GH colors — GUI heatmap will match GH")
            else:
                print(f"[GH] Push failed: {result['error']}")
        except Exception as e:
            print(f"[GH] Push skipped: {e}")

    # ── private helpers ───────────────────────────────────────────────────────

    def _should_use_copilot(self, user_input: str) -> bool:
        keywords = (
            "local", "cost", "area", "rate", "room", "total", "budget",
            "price", "cheap", "expensive", "compare", "heatmap", "calculate",
            "finish", "floor", "wall", "ceiling", "marble", "tile", "wood",
            "reduce", "save",
            "slab", "thickness", "rc_solid", "rc_waffle", "rc_ribbed",
            "post_tensioned", "hollow_core", "composite_steel", "precast",
            "timber_joist", "mm", " m ",
        )
        lower = user_input.lower()
        return any(k in lower for k in keywords)

    def _should_compare_plans(self, user_input: str, plans: dict[str, dict] | None = None) -> bool:
        lower = user_input.lower()
        comparison_keywords = (
            "compare plans",
            "plan comparison",
            "comparison",
            "total-cost comparison",
            "total cost comparison",
            "all plans",
            "each plan",
            "five plans",
            "plans total",
            "plan totals",
            "cost for each plan",
            "which plan is cheapest",
            "which plan is most expensive",
            "cheapest plan",
            "most expensive plan",
        )
        if any(k in lower for k in comparison_keywords):
            return True

        # If multiple plans are available, treat plan-ranking language as a plan comparison.
        if plans and len(plans) > 1:
            if any(k in lower for k in ("cheapest", "most expensive", "highest cost", "lowest cost")):
                if "plan" in lower or "plans" in lower:
                    return True

        return False

    def _compare_plans(self, user_input: str, plans: dict[str, dict], active_plan_key: str | None) -> str:
        rows: list[tuple[str, float, str, int]] = []
        for plan_name, layout in plans.items():
            proj = layout.get("project", {})
            rooms = layout.get("rooms", [])
            currency = proj.get("currency", "")
            totals = layout.get("totals", {})
            room_total = totals.get("rooms", sum((r.get("total_cost", 0) or 0) for r in rooms))
            grand = totals.get("grand", room_total)
            rows.append((plan_name, float(grand), currency, len(rooms)))

        if not rows:
            return "No saved plans are available for comparison yet."

        rows.sort(key=lambda item: item[1])
        cheapest_name, cheapest_total, currency, _ = rows[0]
        active_label = f"Active plan: {active_plan_key}\n\n" if active_plan_key else ""

        lines = [active_label + "**Total cost comparison for saved plans:**", ""]
        for plan_name, grand, plan_currency, room_count in rows:
            delta = grand - cheapest_total
            delta_pct = 0.0 if cheapest_total == 0 else (delta / cheapest_total) * 100.0
            lines.append(
                f"- {plan_name}: {grand:,.0f} {plan_currency} "
                f"({delta:,.0f} above cheapest, {delta_pct:.1f}% diff, {room_count} rooms)"
            )

        if len(rows) > 1:
            most_expensive_name, most_expensive_total, _, _ = rows[-1]
            spread = most_expensive_total - cheapest_total
            spread_pct = 0.0 if cheapest_total == 0 else (spread / cheapest_total) * 100.0
            lines.extend([
                "",
                f"Cheapest: {cheapest_name} at {cheapest_total:,.0f} {currency}",
                f"Most expensive: {most_expensive_name} at {most_expensive_total:,.0f} {currency}",
                f"Spread: {spread:,.0f} {currency} ({spread_pct:.1f}%)",
            ])

        if active_plan_key and active_plan_key in plans:
            active_layout = plans[active_plan_key]
            active_total = active_layout.get("totals", {}).get(
                "grand",
                sum((r.get("total_cost", 0) or 0) for r in active_layout.get("rooms", [])),
            )
            lines.extend([
                "",
                f"I can also compare the active plan ({active_plan_key}) against any other plan if you ask.",
                f"Active plan total: {active_total:,.0f} {active_layout.get('project', {}).get('currency', currency)}",
            ])

        return "\n".join(lines)

    def _build_context(
        self,
        user_input: str,
        layout: dict | None,
        plans: dict[str, dict] | None,
        active_plan_key: str | None,
        history: list[dict] | None,
    ) -> dict:
        ctx: dict = {"user_input": user_input}
        if layout:
            ctx["layout_summary"] = self._summarise_layout(layout)
            ctx["layout_json"] = json.dumps(layout)
        if plans:
            ctx["plans"] = plans
            if active_plan_key and active_plan_key in plans:
                ctx["active_plan_key"] = active_plan_key
        if history:
            ctx["history"] = history[-10:]
        return ctx

    @staticmethod
    def _summarise_layout(layout: dict) -> str:
        proj = layout.get("project", {})
        rooms = layout.get("rooms", [])
        currency = proj.get("currency", "")
        total = sum(r.get("total_cost", 0) for r in rooms)
        room_lines = "\n".join(
            f"  {r.get('name')}: {r.get('area_m2', 0):.1f} m² "
            f"@ {r.get('rate_per_m2', 0):,.0f} {currency}/m² "
            f"= {r.get('total_cost', 0):,.0f} {currency}"
            for r in rooms
        )
        return (
            f"Project: {proj.get('name')} | Currency: {currency} | "
            f"Total: {total:,.0f} {currency}\nRooms:\n{room_lines}"
        )
