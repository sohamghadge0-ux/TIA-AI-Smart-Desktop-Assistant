# ╔══════════════════════════════════════════════════════════════════╗
# ║           TIA AI — MICROSOFT OFFICE TOOLS                       ║
# ║           File: Tools/ms_office_handling.py                     ║
# ║           Handles: Word document creation, PowerPoint           ║
# ║           presentations, Excel file creation                    ║
# ║           Libraries: python-docx, python-pptx, openpyxl         ║
# ║           AI content via Groq LLM                               ║
# ║           Copyright (c) 2025 Soham Ghadge                       ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
import os
import subprocess
import time

import pyautogui
import pyperclip
import requests
from livekit.agents import function_tool


# ──────────────────────────────────────────────────────────────────
#  INTERNAL: Groq for AI-generated content
# ──────────────────────────────────────────────────────────────────

def _groq(prompt: str, max_tokens: int = 2500) -> str:
    """Generate document/slide content via Groq LLM."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return "❌ GROQ_API_KEY missing in .env"
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.6
            },
            timeout=20
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.Timeout:
        return "❌ Groq timed out — try again Boss"
    except Exception as e:
        return f"❌ Groq error: {e}"


# ──────────────────────────────────────────────────────────────────
#  MICROSOFT WORD
#  Creates formatted .docx file with AI-generated content
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def create_word_document(topic: str, filename: str = "") -> str:
    """Create Word document from topic."""
    def _do():
        try:
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            # Set default filename if not provided
            fname = filename if filename else topic.replace(" ", "_")[:30] + ".docx"
            path = os.path.join(os.path.expanduser("~"), "Documents", fname)

            # Generate content with Groq
            content = _groq(
                f"Write a well-structured document about: {topic}\n"
                f"Include: title, introduction, 3-5 sections with headings, conclusion.\n"
                f"Use ## for main headings, # for subheadings."
            )

            # Build the document
            doc = Document()
            title_para = doc.add_heading(topic.title(), 0)
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("##") or (line.startswith("**") and line.endswith("**")):
                    doc.add_heading(line.replace("#", "").replace("*", "").strip(), level=1)
                elif line.startswith("#"):
                    doc.add_heading(line.replace("#", "").strip(), level=2)
                else:
                    p = doc.add_paragraph(line)
                    p.paragraph_format.space_after = Pt(6)

            doc.save(path)
            os.startfile(path)
            return f"✅ Word document created: {path}"

        except ImportError:
            return "❌ Run: pip install python-docx"
        except Exception as e:
            return f"❌ {e}"

    return await asyncio.to_thread(_do)


# ──────────────────────────────────────────────────────────────────
#  MICROSOFT POWERPOINT
#  Creates .pptx with AI-generated slide content
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def create_powerpoint_presentation(
    topic: str,
    slides: int = 6,
    filename: str = ""
) -> str:
    """Create PowerPoint from topic."""
    def _do():
        try:
            from pptx import Presentation
            from pptx.util import Inches
            import json

            fname = filename if filename else topic.replace(" ", "_")[:30] + ".pptx"
            path = os.path.join(os.path.expanduser("~"), "Documents", fname)

            # Ask Groq for structured slide data in JSON
            slide_data = _groq(
                f"Create {slides} PowerPoint slides for: {topic}\n"
                f"Return ONLY valid JSON array:\n"
                f'[{{"title":"Slide Title","content":["point 1","point 2"],"notes":"speaker notes"}}]\n'
                f"Make it professional.",
                max_tokens=2000
            )

            # Clean JSON (remove markdown fences if present)
            if "```json" in slide_data:
                slide_data = slide_data.split("```json")[1].split("```")[0]
            elif "```" in slide_data:
                slide_data = slide_data.split("```")[1].split("```")[0]

            try:
                slides_json = json.loads(slide_data.strip())
            except json.JSONDecodeError:
                slides_json = [{
                    "title": topic,
                    "content": ["Introduction", "Key Points", "Conclusion"],
                    "notes": ""
                }]

            # Build the presentation
            prs = Presentation()
            prs.slide_width  = Inches(13.33)
            prs.slide_height = Inches(7.5)

            for i, slide_info in enumerate(slides_json):
                if i == 0:
                    # Title slide
                    layout = prs.slide_layouts[0]
                    slide = prs.slides.add_slide(layout)
                    slide.shapes.title.text = slide_info.get("title", topic)
                    if slide.placeholders[1]:
                        slide.placeholders[1].text = "\n".join(
                            slide_info.get("content", [])
                        )
                else:
                    # Content slide
                    layout = prs.slide_layouts[1]
                    slide = prs.slides.add_slide(layout)
                    slide.shapes.title.text = slide_info.get("title", f"Slide {i+1}")
                    tf = slide.placeholders[1].text_frame
                    tf.clear()
                    for j, point in enumerate(slide_info.get("content", [])):
                        if j == 0:
                            tf.paragraphs[0].text = point
                        else:
                            p = tf.add_paragraph()
                            p.text = point

                # Add speaker notes
                notes = slide_info.get("notes", "")
                if notes:
                    slide.notes_slide.notes_text_frame.text = notes

            prs.save(path)
            os.startfile(path)
            return f"✅ Presentation created ({len(slides_json)} slides): {path}"

        except ImportError:
            return "❌ Run: pip install python-pptx"
        except Exception as e:
            return f"❌ {e}"

    return await asyncio.to_thread(_do)


# ──────────────────────────────────────────────────────────────────
#  MICROSOFT EXCEL
#  Creates .xlsx file and opens it
# ──────────────────────────────────────────────────────────────────

@function_tool()
async def create_excel_file(filename: str = "tia_data.xlsx") -> str:
    """Create new Excel file."""
    def _do():
        path = os.path.join(os.path.expanduser("~"), "Documents", filename)
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            wb.save(path)
            os.startfile(path)
        except ImportError:
            # openpyxl not installed — just open Excel with empty file
            subprocess.Popen(f'excel "{path}"', shell=True)
        return f"✅ Excel created: {path}"

    return await asyncio.to_thread(_do)
# ╔══════════════════════════════════════════════════════════════════╗
# ║  TIA AI — MICROSOFT OFFICE                                      ║
# ║  Handles: Word, PowerPoint, Excel creation with AI content      ║
# ║  Libraries: python-docx, python-pptx, openpyxl                  ║
# ║  Copyright (c) 2025 Soham Ghadge                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio, os, subprocess
import requests
from livekit.agents import function_tool

def _groq(prompt: str, tokens: int = 2500) -> str:
    key = os.getenv("GROQ_API_KEY","").strip()
    if not key: return "❌ GROQ_API_KEY missing"
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],
                  "max_tokens":tokens,"temperature":0.6},
            timeout=20)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.Timeout: return "❌ Groq timeout"
    except Exception as e: return f"❌ {e}"

@function_tool()
async def create_word_document(topic: str, filename: str = "") -> str:
    """Create Word document from topic."""
    def _do():
        try:
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            fname = filename if filename else topic.replace(" ","_")[:30]+".docx"
            path = os.path.join(os.path.expanduser("~"),"Documents",fname)
            content = _groq(f"Write structured document about: {topic}\nUse ## for headings.")
            doc = Document()
            t = doc.add_heading(topic.title(), 0); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for line in content.split("\n"):
                line = line.strip()
                if not line: continue
                if line.startswith("##") or (line.startswith("**") and line.endswith("**")):
                    doc.add_heading(line.replace("#","").replace("*","").strip(), level=1)
                elif line.startswith("#"):
                    doc.add_heading(line.replace("#","").strip(), level=2)
                else:
                    p = doc.add_paragraph(line); p.paragraph_format.space_after = Pt(6)
            doc.save(path); os.startfile(path)
            return f"✅ Word doc created: {path}"
        except ImportError: return "❌ pip install python-docx"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)

@function_tool()
async def create_powerpoint_presentation(topic: str, slides: int = 6, filename: str = "") -> str:
    """Create PowerPoint from topic."""
    def _do():
        try:
            from pptx import Presentation
            from pptx.util import Inches
            import json
            fname = filename if filename else topic.replace(" ","_")[:30]+".pptx"
            path = os.path.join(os.path.expanduser("~"),"Documents",fname)
            data = _groq(f'Create {slides} slides for: {topic}\nReturn ONLY JSON array: [{{"title":"","content":[""],"notes":""}}]', 2000)
            if "```json" in data: data = data.split("```json")[1].split("```")[0]
            elif "```" in data: data = data.split("```")[1].split("```")[0]
            try: sj = json.loads(data.strip())
            except: sj = [{"title":topic,"content":["Introduction","Key Points","Conclusion"],"notes":""}]
            prs = Presentation(); prs.slide_width=Inches(13.33); prs.slide_height=Inches(7.5)
            for i, si in enumerate(sj):
                if i==0:
                    s = prs.slides.add_slide(prs.slide_layouts[0])
                    s.shapes.title.text = si.get("title",topic)
                    if s.placeholders[1]: s.placeholders[1].text="\n".join(si.get("content",[]))
                else:
                    s = prs.slides.add_slide(prs.slide_layouts[1])
                    s.shapes.title.text = si.get("title",f"Slide {i+1}")
                    tf = s.placeholders[1].text_frame; tf.clear()
                    for j, pt in enumerate(si.get("content",[])):
                        if j==0: tf.paragraphs[0].text=pt
                        else: p=tf.add_paragraph(); p.text=pt
                notes = si.get("notes","")
                if notes: s.notes_slide.notes_text_frame.text=notes
            prs.save(path); os.startfile(path)
            return f"✅ Presentation created ({len(sj)} slides): {path}"
        except ImportError: return "❌ pip install python-pptx"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_do)

@function_tool()
async def create_excel_file(filename: str = "tia_data.xlsx") -> str:
    """Create new Excel file."""
    def _do():
        path = os.path.join(os.path.expanduser("~"),"Documents",filename)
        try:
            import openpyxl; wb=openpyxl.Workbook(); wb.save(path); os.startfile(path)
        except: subprocess.Popen(f'excel "{path}"', shell=True)
        return f"✅ Excel created: {path}"
    return await asyncio.to_thread(_do)