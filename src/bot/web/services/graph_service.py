"""Service for querying, formatting, and styling the Neo4j knowledge graph."""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import GraphDatabase

from bot.config import Settings
from bot.log import get_logger

logger = get_logger(__name__)


def _serialize_neo4j_val(val: Any) -> Any:
    """Recursively convert Neo4j types (dates, spatial, etc.) to JSON-safe primitives."""
    if val is None:
        return None
    if isinstance(val, int | float | bool | str):
        return val
    if isinstance(val, list | tuple):
        return [_serialize_neo4j_val(x) for x in val]
    if isinstance(val, dict):
        return {k: _serialize_neo4j_val(v) for k, v in val.items()}
    return str(val)


class GraphVisualizerService:
    """Encapsulates Cypher queries and visual representation logic for Vis.js Network."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _classify_node(self, labels: list[str], props: dict[str, Any]) -> dict[str, Any]:
        """Classify node category, icon, color palette, and geometric shape."""
        labels_lower = [lbl.lower() for lbl in labels]
        name = (
            props.get("name")
            or props.get("title")
            or props.get("source_description")
            or props.get("content")
            or (labels[0] if labels else "Node")
        )
        display_label = str(name)
        if len(display_label) > 24:
            display_label = display_label[:21] + "..."

        if "episodic" in labels_lower:
            return {
                "group": "Episodic",
                "icon": "💬",
                "color": {"background": "#7c3aed", "border": "#a78bfa"},
                "shape": "diamond",
                "size": 18,
                "display_label": display_label,
                "full_name": str(name),
            }
        if "community" in labels_lower:
            return {
                "group": "Community",
                "icon": "🌐",
                "color": {"background": "#d97706", "border": "#fbbf24"},
                "shape": "hexagon",
                "size": 26,
                "display_label": display_label,
                "full_name": str(name),
            }
        if any(lbl in labels_lower for lbl in ("person", "user", "member", "human")):
            return {
                "group": "Person",
                "icon": "👤",
                "color": {"background": "#059669", "border": "#34d399"},
                "shape": "dot",
                "size": 26,
                "display_label": display_label,
                "full_name": str(name),
            }
        if any(lbl in labels_lower for lbl in ("animal", "pet", "creature", "dog", "cat")):
            return {
                "group": "Animal",
                "icon": "🐾",
                "color": {"background": "#9333ea", "border": "#c084fc"},
                "shape": "dot",
                "size": 24,
                "display_label": display_label,
                "full_name": str(name),
            }
        if any(
            lbl in labels_lower
            for lbl in ("item", "object", "product", "vehicle", "tool", "device")
        ):
            return {
                "group": "Item",
                "icon": "📦",
                "color": {"background": "#2563eb", "border": "#60a5fa"},
                "shape": "dot",
                "size": 23,
                "display_label": display_label,
                "full_name": str(name),
            }
        if any(lbl in labels_lower for lbl in ("location", "place", "city", "country", "venue")):
            return {
                "group": "Location",
                "icon": "📍",
                "color": {"background": "#ea580c", "border": "#fb923c"},
                "shape": "dot",
                "size": 24,
                "display_label": display_label,
                "full_name": str(name),
            }
        if any(
            lbl in labels_lower
            for lbl in ("concept", "hobby", "skill", "event", "sport", "interest", "activity")
        ):
            return {
                "group": "Concept",
                "icon": "💡",
                "color": {"background": "#ca8a04", "border": "#fde047"},
                "shape": "dot",
                "size": 22,
                "display_label": display_label,
                "full_name": str(name),
            }

        return {
            "group": "Entity",
            "icon": "⚪",
            "color": {"background": "#0284c7", "border": "#38bdf8"},
            "shape": "dot",
            "size": 22,
            "display_label": display_label,
            "full_name": str(name),
        }

    def fetch_graph_data(
        self, chat_id: int | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Synchronously query Neo4j for nodes and relations (executed in executor thread)."""
        if not self.settings.neo4j_password:
            return [], []

        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        nodes_dict: dict[str, dict[str, Any]] = {}
        edges_dict: dict[str, dict[str, Any]] = {}

        try:
            with driver.session() as session:
                # If chat_id is given, scope query by group_id property if available
                query = """
                    MATCH (n)
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN n, r, m
                    LIMIT 300
                """
                params: dict[str, Any] = {}
                if chat_id is not None:
                    query = """
                        MATCH (n)
                        WHERE n.group_id = $group_id
                        OPTIONAL MATCH (n)-[r]->(m)
                        WHERE m.group_id = $group_id OR m IS NULL
                        RETURN n, r, m
                        LIMIT 300
                    """
                    params["group_id"] = str(chat_id)

                result = session.run(query, params)
                for record in result:
                    n = record.get("n")
                    r = record.get("r")
                    m = record.get("m")

                    for node_obj in (n, m):
                        if node_obj is not None and node_obj.element_id not in nodes_dict:
                            labels = list(node_obj.labels)
                            props = {k: _serialize_neo4j_val(v) for k, v in dict(node_obj).items()}
                            meta = self._classify_node(labels, props)

                            nodes_dict[node_obj.element_id] = {
                                "id": node_obj.element_id,
                                "label": f"{meta['icon']} {meta['display_label']}",
                                "raw_label": meta["display_label"],
                                "icon": meta["icon"],
                                "full_name": meta["full_name"],
                                "labels": labels,
                                "group": meta["group"],
                                "color": meta["color"],
                                "shape": meta["shape"],
                                "size": meta["size"],
                                "font": {"color": "#ffffff", "face": "system-ui, sans-serif"},
                                "properties": props,
                            }

                    if (
                        r is not None
                        and r.element_id not in edges_dict
                        and n is not None
                        and m is not None
                    ):
                        r_props = {k: _serialize_neo4j_val(v) for k, v in dict(r).items()}
                        fact = r_props.get("fact") or r_props.get("name") or ""
                        rel_label = (
                            str(fact)[:28] + ("..." if len(str(fact)) > 28 else "")
                            if fact
                            else r.type
                        )

                        edges_dict[r.element_id] = {
                            "id": r.element_id,
                            "from": n.element_id,
                            "to": m.element_id,
                            "label": rel_label,
                            "type": r.type,
                            "full_fact": str(fact) if fact else r.type,
                            "properties": r_props,
                            "arrows": "to",
                            "color": {
                                "color": "#64748b",
                                "highlight": "#38bdf8",
                                "hover": "#94a3b8",
                            },
                            "font": {"size": 10, "color": "#94a3b8", "background": "#0f172a"},
                        }
        finally:
            driver.close()

        return list(nodes_dict.values()), list(edges_dict.values())

    async def get_graph(self, chat_id: int | None = None) -> dict[str, Any]:
        """Async entry point returning node and edge collections."""
        nodes, edges = await asyncio.to_thread(self.fetch_graph_data, chat_id)
        return {
            "success": True,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "nodes_count": len(nodes),
                "edges_count": len(edges),
            },
        }
