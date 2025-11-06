# -*- coding: utf-8 -*-
"""Create a 3-page Japanese PDF fixture for multi-page upload testing."""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from pathlib import Path

pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))

out = Path(__file__).parent / "test_japanese_multipage.pdf"

c = canvas.Canvas(str(out), pagesize=A4)
width, height = A4

pages = [
    {
        "title": "Page 1: Introduction",
        "lines": [
            "\u6771\u4eac\u306f\u65e5\u672c\u306e\u9996\u90fd\u3067\u3059\u3002",
            "\u4eba\u53e3\u306f\u7d041400\u4e07\u4eba\u3067\u3001\u4e16\u754c\u6700\u5927\u306e\u90fd\u5e02\u570f\u306e\u4e00\u3064\u3067\u3059\u3002",
            "\u6771\u4eac\u30bf\u30ef\u30fc\u3084\u30b9\u30ab\u30a4\u30c4\u30ea\u30fc\u306a\u3069\u306e\u6709\u540d\u306a\u30e9\u30f3\u30c9\u30de\u30fc\u30af\u304c\u3042\u308a\u307e\u3059\u3002",
        ]
    },
    {
        "title": "Page 2: Culture",
        "lines": [
            "\u65e5\u672c\u306e\u6587\u5316\u306f\u975e\u5e38\u306b\u8c4a\u304b\u3067\u591a\u69d8\u3067\u3059\u3002",
            "\u8336\u9053\u3001\u83ef\u9053\u3001\u66f8\u9053\u306a\u3069\u306e\u4f1d\u7d71\u7684\u306a\u82b8\u8853\u304c\u3042\u308a\u307e\u3059\u3002",
            "\u30a2\u30cb\u30e1\u3084\u30de\u30f3\u30ac\u306f\u4e16\u754c\u4e2d\u3067\u4eba\u6c17\u304c\u3042\u308a\u307e\u3059\u3002",
        ]
    },
    {
        "title": "Page 3: Technology",
        "lines": [
            "\u65e5\u672c\u306f\u6280\u8853\u9769\u65b0\u306e\u5206\u91ce\u3067\u30ea\u30fc\u30c0\u30fc\u3067\u3059\u3002",
            "\u65b0\u5e79\u7dda\u306f\u4e16\u754c\u3067\u6700\u3082\u901f\u3044\u5217\u8eca\u306e\u4e00\u3064\u3067\u3059\u3002",
            "\u30ed\u30dc\u30c3\u30c8\u5de5\u5b66\u3068\u4eba\u5de5\u77e5\u80fd\u306e\u7814\u7a76\u304c\u76db\u3093\u3067\u3059\u3002",
        ]
    },
]

for i, page in enumerate(pages):
    if i > 0:
        c.showPage()
    c.setFont('Helvetica-Bold', 16)
    c.drawString(72, height - 72, page["title"])
    c.setFont('HeiseiMin-W3', 14)
    y = height - 120
    for line in page["lines"]:
        c.drawString(72, y, line)
        y -= 30

c.save()
print(f"Created: {out} ({out.stat().st_size} bytes, {len(pages)} pages)")

# Also create individual single-page PDFs for sequential upload testing
for i, page in enumerate(pages):
    single = out.parent / f"test_japanese_page{i+1}.pdf"
    sc = canvas.Canvas(str(single), pagesize=A4)
    sc.setFont('Helvetica-Bold', 16)
    sc.drawString(72, height - 72, page["title"])
    sc.setFont('HeiseiMin-W3', 14)
    y = height - 120
    for line in page["lines"]:
        sc.drawString(72, y, line)
        y -= 30
    sc.save()
    print(f"Created: {single} ({single.stat().st_size} bytes)")

