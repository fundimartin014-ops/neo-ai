import logging
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XMLParseSkill:
    """
    Parse XML and optionally evaluate a limited XPath subset.
    Inputs:
      xml    (required)
      xpath  (optional: "root/child/grandchild")
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        xml = inputs.get("xml", "")
        if not xml:
            return {"error": "xml is required"}
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            return {"error": f"Invalid XML: {e}"}

        xpath = inputs.get("xpath")
        if xpath:
            try:
                found = root.findall(str(xpath))
                results = [
                    {"tag": e.tag, "text": (e.text or "").strip(), "attrib": e.attrib}
                    for e in found
                ]
                return {"results": results, "count": len(results)}
            except Exception as e:
                return {"error": f"XPath failed: {e}"}

        # Full tree summary
        def _node(e):
            return {
                "tag": e.tag,
                "attrib": e.attrib,
                "text": (e.text or "").strip(),
                "children": [_node(c) for c in e],
            }

        return {"root": _node(root)}