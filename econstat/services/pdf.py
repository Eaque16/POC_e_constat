from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_claim_pdf(claim_id: str, data: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"constat-{claim_id}.pdf"
    doc = SimpleDocTemplate(str(target), pagesize=A4, title=f"E-Constat {claim_id}")
    styles = getSampleStyleSheet()
    rows = [["Champ", "Valeur"]] + [
        [k.replace("_", " ").title(), str(v)] for k, v in data.items() if v not in (None, "", [])
    ]
    table = Table(rows, colWidths=[170, 340], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    doc.build(
        [
            Paragraph("Déclaration automobile — E-Constat IA", styles["Title"]),
            Spacer(1, 12),
            Paragraph("Document validé par un agent humain.", styles["Normal"]),
            Spacer(1, 16),
            table,
        ]
    )
    return target
