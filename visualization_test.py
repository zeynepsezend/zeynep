from pathlib import Path
import json

import plotly.graph_objects as go
import streamlit as st


DEFAULT_LAYOUT_PATH = Path("./layout_input/layout_schema.json")


def parse_xy_pairs(geometry):
	"""Return x/y lists from a list of [x, y] coordinate pairs."""
	if not isinstance(geometry, list):
		return [], []

	xs, ys = [], []
	for pt in geometry:
		if isinstance(pt, (list, tuple)) and len(pt) >= 2:
			try:
				xs.append(float(pt[0]))
				ys.append(float(pt[1]))
			except (TypeError, ValueError):
				continue
	return xs, ys


def add_line_layer(fig, items, name, color, width=3, dash=None):
	for idx, item in enumerate(items):
		geom = item.get("geometry", []) if isinstance(item, dict) else []
		xs, ys = parse_xy_pairs(geom)
		if len(xs) < 2:
			continue

		fig.add_trace(
			go.Scatter(
				x=xs,
				y=ys,
				mode="lines",
				line={"color": color, "width": width, "dash": dash} if dash else {"color": color, "width": width},
				name=name,
				legendgroup=name,
				showlegend=idx == 0,
				hovertemplate=(
					f"{name}<br>"
					f"id: {item.get('id', 'n/a')}<br>"
					f"name: {item.get('name', 'n/a')}"
					"<extra></extra>"
				),
			)
		)


def add_polygon_layer(fig, items, name, line_color, fill_color):
	for idx, item in enumerate(items):
		geom = item.get("geometry", []) if isinstance(item, dict) else []
		xs, ys = parse_xy_pairs(geom)
		if len(xs) < 3:
			continue

		fig.add_trace(
			go.Scatter(
				x=xs,
				y=ys,
				mode="lines",
				fill="toself",
				line={"color": line_color, "width": 2},
				fillcolor=fill_color,
				name=name,
				legendgroup=name,
				showlegend=idx == 0,
				hovertemplate=(
					f"{name}<br>"
					f"id: {item.get('id', 'n/a')}<br>"
					f"name: {item.get('name', 'n/a')}"
					"<extra></extra>"
				),
			)
		)


def add_room_labels(fig, rooms):
	for room in rooms:
		geom = room.get("geometry", []) if isinstance(room, dict) else []
		xs, ys = parse_xy_pairs(geom)
		if len(xs) < 3:
			continue

		# Ignore duplicated closing vertex for centroid approximation.
		if len(xs) >= 2 and xs[0] == xs[-1] and ys[0] == ys[-1]:
			centroid_x = sum(xs[:-1]) / max(len(xs) - 1, 1)
			centroid_y = sum(ys[:-1]) / max(len(ys) - 1, 1)
		else:
			centroid_x = sum(xs) / len(xs)
			centroid_y = sum(ys) / len(ys)

		room_name = room.get("name") or room.get("id") or "Room"
		fig.add_trace(
			go.Scatter(
				x=[centroid_x],
				y=[centroid_y],
				mode="text",
				text=[room_name],
				textposition="middle center",
				textfont={"size": 12, "color": "#111827"},
				name="Room Labels",
				legendgroup="Room Labels",
				showlegend=False,
				hoverinfo="skip",
			)
		)


def build_layout_figure(layout, show_labels=True):
	fig = go.Figure()

	outline = layout.get("outline", []) if isinstance(layout, dict) else []
	rooms = layout.get("rooms", []) if isinstance(layout, dict) else []
	doors = layout.get("doors", []) if isinstance(layout, dict) else []
	windows = layout.get("windows", []) if isinstance(layout, dict) else []
	furniture = layout.get("furniture", []) if isinstance(layout, dict) else []
	mep = layout.get("mep", []) if isinstance(layout, dict) else []
	structure = layout.get("structure", []) if isinstance(layout, dict) else []

	x_outline, y_outline = parse_xy_pairs(outline)
	if len(x_outline) >= 3:
		fig.add_trace(
			go.Scatter(
				x=x_outline,
				y=y_outline,
				mode="lines",
				fill="toself",
				line={"color": "#0f172a", "width": 3},
				fillcolor="rgba(148, 163, 184, 0.18)",
				name="Outline",
				hovertemplate="Outline<extra></extra>",
			)
		)

	add_polygon_layer(fig, rooms, "Rooms", "#1d4ed8", "rgba(59, 130, 246, 0.18)")
	add_line_layer(fig, structure, "Structure", "#111827", width=4)
	add_line_layer(fig, doors, "Doors", "#dc2626", width=5)
	add_line_layer(fig, windows, "Windows", "#0284c7", width=4)
	add_polygon_layer(fig, furniture, "Furniture", "#16a34a", "rgba(22, 163, 74, 0.20)")
	add_polygon_layer(fig, mep, "MEP", "#ea580c", "rgba(249, 115, 22, 0.20)")

	if show_labels:
		add_room_labels(fig, rooms)

	fig.update_layout(
		template="plotly_white",
		margin={"l": 20, "r": 20, "t": 50, "b": 20},
		title={
			"text": f"Layout: {layout.get('layoutId', 'Unnamed Layout')}",
			"x": 0.02,
			"y": 0.98,
			"xanchor": "left",
			"yanchor": "top",
		},
		legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
		xaxis={"title": "X", "showgrid": True, "zeroline": False, "scaleanchor": "y", "scaleratio": 1},
		yaxis={"title": "Y", "showgrid": True, "zeroline": False},
	)
	return fig


def load_layout_from_path(layout_path):
	with layout_path.open("r", encoding="utf-8") as f:
		return json.load(f)


def main():
	st.set_page_config(page_title="2D Layout Visualizer", layout="wide")
	st.title("2D Layout Visualizer")
	st.caption("Streamlit + Plotly viewer for layout JSON files")

	with st.sidebar:
		st.header("Data Source")
		use_uploader = st.toggle("Upload JSON file", value=False)

		layout_data = None
		selected_path = DEFAULT_LAYOUT_PATH

		if use_uploader:
			uploaded = st.file_uploader("Upload layout JSON", type=["json"])
			if uploaded is not None:
				try:
					layout_data = json.load(uploaded)
				except json.JSONDecodeError as exc:
					st.error(f"Invalid JSON: {exc}")
					st.stop()
		else:
			custom_path = st.text_input("Layout path", value=str(DEFAULT_LAYOUT_PATH))
			selected_path = Path(custom_path)

		show_labels = st.checkbox("Show room labels", value=True)

	if layout_data is None:
		if not selected_path.exists():
			st.error(f"File not found: {selected_path}")
			st.stop()
		try:
			layout_data = load_layout_from_path(selected_path)
		except json.JSONDecodeError as exc:
			st.error(f"Invalid JSON in file: {exc}")
			st.stop()

	fig = build_layout_figure(layout_data, show_labels=show_labels)
	st.plotly_chart(fig, use_container_width=True)

	with st.expander("Raw layout JSON"):
		st.json(layout_data)


if __name__ == "__main__":
	main()