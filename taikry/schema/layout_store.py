"""
Diagram Layout Storage for ZYROX AI Schema Designer.
Safely stores visual node positions (x, y), canvas zoom, pan offsets, and domain groupings
completely decoupled from database DDL.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("taikry.schema.layout_store")

LAYOUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "diagram_layout.json")


class DiagramLayoutStore:
    """Manages visual layout coordinates and presentation state."""

    def __init__(self, file_path: str = LAYOUT_FILE_PATH):
        self.file_path = file_path

    def load_layout(self) -> Dict[str, Any]:
        """Loads diagram layout state or generates default grid positions."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to read layout file: {exc}. Using auto-layout.")

        return self.get_default_layout()

    def save_layout(self, layout_data: Dict[str, Any]) -> bool:
        """Persists diagram layout safely without altering database state."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(layout_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error(f"Failed to save layout: {exc}")
            return False

    def get_default_layout(self) -> Dict[str, Any]:
        """Calculates aesthetic auto-layout grid for tables by domain."""
        from taikry.schema.introspector import schema_introspector
        meta = schema_introspector.introspect_all()

        nodes: Dict[str, Any] = {}
        col_idx = 0
        row_idx = 0
        card_w = 320
        card_h = 280
        gap_x = 80
        gap_y = 60
        max_cols = 4

        domains = {}
        for t in meta.get("tables", []):
            d = t.get("domain", "General")
            domains.setdefault(d, []).append(t["name"])

        # Arrange by domain blocks
        base_x = 60
        base_y = 60

        for domain, tbl_names in domains.items():
            for t_name in tbl_names:
                x = base_x + (col_idx % max_cols) * (card_w + gap_x)
                y = base_y + (row_idx) * (card_h + gap_y)

                nodes[t_name] = {
                    "x": x,
                    "y": y,
                    "width": card_w,
                    "domain": domain,
                    "collapsed": False
                }
                col_idx += 1
                if col_idx % max_cols == 0:
                    row_idx += 1

            row_idx += 1
            col_idx = 0

        return {
            "version": 1,
            "viewport": {
                "zoom": 1.0,
                "pan_x": 0,
                "pan_y": 0
            },
            "nodes": nodes,
            "custom_relationships": []
        }


diagram_layout_store = DiagramLayoutStore()

