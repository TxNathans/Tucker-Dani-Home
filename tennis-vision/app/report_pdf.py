"""A swing or serve read as a PDF that can be saved, printed or sent to a player."""
from __future__ import annotations

import time
from pathlib import Path

from fpdf import FPDF

INK, INK2, MUTED, HAIR = (29, 37, 54), (85, 96, 120), (135, 145, 166), (222, 226, 234)
BLUE = (10, 92, 245)
GRADE = {"strength": ((37, 184, 102), "Strength"), "on_target": ((59, 130, 246), "On target"), "building": ((242, 165, 22), "Building"),
         "priority": ((238, 87, 87), "Priority"), "not_graded": ((164, 172, 189), "Not graded")}
SWAPS = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "→": "to", "×": "x"}


def _t(text) -> str:
    """Text the built-in PDF fonts can draw."""
    s = str(text if text is not None else "")
    for a, b in SWAPS.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _value(v, unit: str) -> str:
    if isinstance(v, (int, float)):
        num = str(v) if isinstance(v, int) or float(v).is_integer() else f"{v:.2f}".rstrip("0").rstrip(".")
        return f"{num}°" if unit == "deg" else f"{num} {unit}".strip()
    return str(v if v is not None else "-")


def swing_name(s: dict) -> str:
    serve = s.get("serve") or {}
    if serve.get("type") in ("flat", "slice", "kick"):
        return f"{serve['type'].capitalize()} serve"
    return s["stroke"].capitalize() + (", two-handed" if s.get("two_handed") else "")


class _Doc(FPDF):
    def footer(self):
        self.set_y(-11)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _t(f"Tracer Tennis   |   page {self.page_no()}"), align="C")


def build_pdf(job: dict, report: dict, swing: dict, folder: Path, notes: str = "") -> bytes:
    c = swing.get("coaching") or {}
    grades, sure = c.get("grades", {}), c.get("confidence", {})
    pdf = _Doc(format="letter", unit="mm")
    pdf.set_auto_page_break(True, margin=14)
    pdf.set_margins(14, 13, 14)
    pdf.add_page()
    W = pdf.w - 28

    def text(size, color=INK, style=""):
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*color)

    def para(body, size=10, color=INK, style="", gap=1.5, width=W, line=None):
        text(size, color, style)
        pdf.multi_cell(width, line or size * 0.47, _t(body), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    def heading(label):
        if pdf.get_y() > pdf.h - 40:
            pdf.add_page()
        pdf.ln(2)
        text(8.5, MUTED, "B")
        pdf.cell(W, 5, _t(label.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*HAIR)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
        pdf.ln(2.5)

    def dot(grade, x, y, r=1.25):
        pdf.set_fill_color(*GRADE.get(grade, GRADE["not_graded"])[0])
        pdf.ellipse(x - r, y - r, 2 * r, 2 * r, style="F")

    # header
    text(8.5, BLUE, "B")
    pdf.cell(W, 4.5, "TRACER TENNIS", new_x="LMARGIN", new_y="NEXT")
    text(20, INK, "B")
    pdf.cell(W, 9.5, _t(swing_name(swing)), new_x="LMARGIN", new_y="NEXT")
    made = time.strftime("%b %d, %Y", time.localtime(job.get("created", time.time())))
    text(9.5, INK2)
    pdf.cell(W, 5, _t(f"{job.get('title', '')}   |   {made}   |   {swing.get('hand', '')}-handed   |   {round(report['video']['fps'])} fps"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    fixes = c.get("fixes") or []
    top = fixes[0] if fixes else None
    y0 = pdf.get_y()
    shot = folder / (report.get("keyframes", {}).get(f"{swing['index']}:contact") or "")
    left = W - 50 if shot.is_file() else W
    if shot.is_file():
        pdf.image(str(shot), x=pdf.l_margin + W - 45, y=y0, w=45)
    if c:
        counts = c.get("counts", {})
        para(top.get("problem") or top["title"] if top else "Nothing to fix on this one.", 15, INK, "B", 1.5, left, 6.6)
        para(top["why"] if top else "Every number we grade came out on target.", 10, INK2, "", 2, left)
        on = counts.get("on_target", 0)
        para(f"{on} of {counts.get('graded', 0)} graded numbers on target.   Priority {counts.get('priority', 0)}   |   "
             f"Building {counts.get('building', 0)}   |   Strength {counts.get('strength', 0)}", 9.5, INK, "B", 2, left)
        if c.get("context"):
            para(c["context"], 8.5, MUTED, "", 2, left)
    if shot.is_file():
        pdf.set_y(max(pdf.get_y(), y0 + 62))

    if top:
        heading("Work on first")
        for n, f in enumerate(fixes[:3]):
            if pdf.get_y() > pdf.h - 60:
                pdf.add_page()
            y = pdf.get_y()
            dot(f.get("grade", "building"), pdf.l_margin + 1.4, y + 2.4)
            pdf.set_x(pdf.l_margin + 5)
            text(11, INK, "B")
            pdf.cell(W - 5, 5, _t(f"{n + 1}. {f['title']}"), new_x="LMARGIN", new_y="NEXT")
            sure_note = "  (estimate)" if f.get("confidence") == "estimate" else ""
            para(f"{f['label'].split(' (')[0]}: {_value(f['value'], f['unit'])}   |   target {f.get('typical', '')}{sure_note}", 8.5, MUTED, "", 1)
            para(f["saw"], 10, INK, "", 1.2)
            pdf.set_fill_color(*BLUE)
            text(11.5, (255, 255, 255), "B")
            pdf.multi_cell(W, 7.5, _t("  The focus:  " + f["cue"]), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            if f.get("alts"):
                para("Other ways to say it:  " + "   |   ".join(f["alts"]), 9, INK2, "", 1)
            para("Drill:  " + f["drill"], 9.5, INK, "", 1)
            if f.get("check"):
                para("You got it when:  " + f["check"], 9.5, INK, "", 3)

    wins = (c.get("strengths") or [])[:5]
    if wins:
        heading("Already working")
        for w in wins:
            y = pdf.get_y()
            dot(w.get("grade", "on_target"), pdf.l_margin + 1.4, y + 2.2)
            pdf.set_x(pdf.l_margin + 5)
            text(10, INK)
            pdf.multi_cell(W - 5, 4.7, _t(w["text"] + (f"  ({_value(w['value'], w['unit'])})" if isinstance(w.get("value"), (int, float)) else "")),
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)

    if notes.strip():
        heading("Notes")
        para(notes.strip(), 10)

    frames = [(label, folder / report.get("keyframes", {}).get(f"{swing['index']}:{key}", "")) for key, label in (swing.get("phases") or [])[1:]]
    frames = [(label, p) for label, p in frames if p.is_file()]
    if frames:
        if pdf.get_y() > pdf.h - 75:
            pdf.add_page()
        heading("Key moments")
        gap, per = 3, min(len(frames), 5)
        w = (W - gap * (per - 1)) / per
        y = pdf.get_y()
        h_img = 0
        for n, (label, p) in enumerate(frames[:per]):
            x = pdf.l_margin + n * (w + gap)
            info = pdf.image(str(p), x=x, y=y, w=w)
            h_img = max(h_img, info.rendered_height)
            pdf.set_xy(x, y + info.rendered_height + 1)
            text(8, INK2)
            pdf.cell(w, 4, _t(label), align="C")
        pdf.set_y(y + h_img + 7)

    pdf.add_page()
    heading("All numbers")
    cols = [(86, "Number"), (26, "Grade"), (28, "This swing"), (W - 140, "Target")]
    text(8, MUTED, "B")
    for width, label in cols:
        pdf.cell(width, 5, label)
    pdf.ln(6)
    phase = None
    for m in sorted(swing["metrics"], key=lambda m: [x["phase"] for x in swing["metrics"]].index(m["phase"])):
        if pdf.get_y() > pdf.h - (32 if m["phase"] != phase else 21):      # keep a heading with its first row, and a row with its dot
            pdf.add_page()
        if m["phase"] != phase:
            phase = m["phase"]
            pdf.ln(1)
            text(8.5, BLUE, "B")
            pdf.cell(W, 5, _t(phase), new_x="LMARGIN", new_y="NEXT")
        g = grades.get(m["key"], "not_graded")
        y = pdf.get_y()
        text(9, INK)
        pdf.cell(cols[0][0], 5, _t(m["label"].split(" (")[0])[:58])
        dot(g, pdf.get_x() + 1.3, y + 2.5, 1.1)
        pdf.set_x(pdf.get_x() + 4)
        text(8.5, INK2)
        pdf.cell(cols[1][0] - 4, 5, GRADE.get(g, GRADE["not_graded"])[1])
        text(9, INK, "B")
        pdf.cell(cols[2][0], 5, _t(_value(m["value"], m["unit"]) + (" *" if sure.get(m["key"]) == "estimate" else ""))[:18])
        text(8.5, INK2)
        pdf.cell(cols[3][0], 5, _t(m.get("typical", ""))[:34], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    para("* An estimate: worked out in 3D from one camera, read from the racket's outline, or timed between frames. "
         "Use it to compare your own swings filmed from the same spot.", 8, MUTED)
    checks = report.get("checks") or []
    if checks:
        heading("Video check")
        for chk in checks:
            mark = {"good": "OK", "warn": "Note", "bad": "Problem"}.get(chk["status"], "")
            para(f"{chk['label']} ({mark}): {chk['text']}" + (f" {chk['tip']}" if chk.get("tip") and chk["status"] != "good" else ""), 9, INK2, "", 0.8)
    return bytes(pdf.output())


def numbers_csv(swing: dict) -> str:
    import csv
    import io
    c = swing.get("coaching") or {}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Part of the swing", "Number", "Value", "Unit", "Target", "Grade", "How sure", "What it means"])
    for m in swing["metrics"]:
        grade = GRADE.get(c.get("grades", {}).get(m["key"], "not_graded"), GRADE["not_graded"])[1]
        sure = {"high": "seen directly", "estimate": "estimate", "low": "not seen clearly"}.get(m.get("confidence", "high"), "")
        w.writerow([m["phase"], m["label"], m["value"], m["unit"], m.get("typical", ""), grade, sure, m.get("note", "")])
    return out.getvalue()
