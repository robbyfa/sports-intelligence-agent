"""Render a clean portfolio-quality graph diagram."""

import base64
import httpx

mermaid = """---
config:
  flowchart:
    curve: linear
    padding: 20
  theme: base
  themeVariables:
    primaryColor: "#e8e5ff"
    primaryBorderColor: "#7c3aed"
    primaryTextColor: "#1e1b4b"
    lineColor: "#6d28d9"
    secondaryColor: "#f5f3ff"
    tertiaryColor: "#faf5ff"
    fontSize: 14px
---
graph TD
    START(["Start"]):::first
    TE["Tool Execute<br/><i>timeline, stats, summary</i>"]
    ES["Event Search<br/><i>semantic retrieval</i>"]
    GD["Grade Documents<br/><i>relevance check</i>"]
    GEN["Generate Answer<br/><i>sports analyst prompt</i>"]
    WS["Web Search<br/><i>fallback</i>"]
    END(["Answer + Sources"]):::last

    START -. "structured<br/>query" .-> TE
    START -. "semantic<br/>search" .-> ES
    START -. "off-topic" .-> WS

    TE --> GD
    ES --> GD

    GD -. "relevant docs" .-> GEN
    GD -. "no relevant docs" .-> WS

    WS --> GEN

    GEN -. "useful" .-> END
    GEN -. "not grounded" .-> GEN
    GEN -. "not useful" .-> ES

    classDef default fill:#f2f0ff,stroke:#7c3aed,stroke-width:1.5px,color:#1e1b4b
    classDef first fill:#ffffff,stroke:#7c3aed,stroke-width:2px
    classDef last fill:#bfb6fc,stroke:#7c3aed,stroke-width:2px
"""

encoded = base64.urlsafe_b64encode(mermaid.encode("utf-8")).decode("ascii")
url = f"https://mermaid.ink/img/{encoded}"

resp = httpx.get(
    url,
    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    follow_redirects=True,
    timeout=30,
)

if resp.status_code == 200:
    with open("graph.png", "wb") as f:
        f.write(resp.content)
    print(f"Saved graph.png ({len(resp.content)} bytes)")
else:
    print(f"Failed: HTTP {resp.status_code}")
    print(resp.text[:500])
