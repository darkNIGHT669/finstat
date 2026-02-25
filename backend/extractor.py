import re
import json
import os
from typing import Callable, Optional
import pdfplumber
from groq import Groq

from normalizer import normalize_label, CANONICAL_ITEMS

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

IS_KEYWORDS = [
    "revenue", "net revenue", "total revenue", "net sales", "sales",
    "cost of goods", "cost of sales", "cost of revenue", "cogs",
    "gross profit", "gross margin",
    "operating expense", "operating income", "operating profit", "operating loss",
    "research and development", "r&d", "selling", "general and administrative",
    "ebit", "ebitda", "depreciation", "amortization",
    "interest expense", "interest income",
    "income before tax", "pretax income", "earnings before tax",
    "income tax", "provision for tax",
    "net income", "net loss", "net earnings",
    "earnings per share", "eps", "diluted", "basic",
]

CURRENCY_PATTERNS = {
    "USD": [r"\$", r"\bUSD\b", r"U\.S\. [Dd]ollar", r"United States [Dd]ollar"],
    "EUR": [r"€", r"\bEUR\b", r"\bEuro\b"],
    "GBP": [r"£", r"\bGBP\b", r"[Pp]ound [Ss]terling"],
    "INR": [r"₹", r"\bINR\b", r"[Ii]ndian [Rr]upee"],
    "JPY": [r"¥", r"\bJPY\b", r"\b[Yy]en\b"],
    "CNY": [r"\bCNY\b", r"\bRMB\b", r"[Rr]enminbi"],
    "CAD": [r"\bCAD\b", r"[Cc]anadian [Dd]ollar"],
    "AUD": [r"\bAUD\b", r"[Aa]ustralian [Dd]ollar"],
}

UNIT_PATTERNS = {
    "billions": [r"in billions", r"\(billions\)", r"billions of", r"\$.*billion"],
    "millions": [r"in millions", r"\(millions\)", r"millions of", r"\$.*million"],
    "thousands": [r"in thousands", r"\(thousands\)", r"thousands of", r"\$.*thousand"],
}


def score_section(text: str) -> float:
    if not text:
        return 0.0
    lower = text.lower()
    hits = sum(1 for kw in IS_KEYWORDS if kw in lower)
    return hits / len(IS_KEYWORDS)


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    lines = text.split("\n")
    cleaned = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned)


def detect_currency(full_text: str) -> str:
    sample = full_text[:5000]
    for currency, patterns in CURRENCY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, sample):
                return currency
    return "CURRENCY_UNDETECTED"


def detect_unit(full_text: str) -> str:
    sample = full_text[:8000]
    lower = sample.lower()
    for unit, patterns in UNIT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower):
                return unit
    return "units_unknown"


def extract_all_text_and_tables(pdf_path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            tables = page.extract_tables() or []
            table_texts = []
            for table in tables:
                rows = []
                for row in table:
                    if row:
                        cells = [str(c).strip() if c else "" for c in row]
                        rows.append(" | ".join(cells))
                table_texts.append("\n".join(rows))
            pages.append({
                "page": page_num,
                "raw_text": clean_text(raw_text),
                "tables": table_texts,
                "combined": clean_text(raw_text) + "\n" + "\n\n".join(table_texts),
            })
    return pages


def find_candidate_pages(pages: list[dict], threshold: float = 0.18) -> list[dict]:
    scored = [(p, score_section(p["combined"])) for p in pages]
    candidates = [(p, s) for p, s in scored if s >= threshold]
    if not candidates:
        best = max(scored, key=lambda x: x[1])
        candidates = [best] if best[1] > 0 else scored[:5]
    candidates.sort(key=lambda x: x[1], reverse=True)
    top = [p for p, _ in candidates[:8]]
    top.sort(key=lambda p: p["page"])
    return top


def build_candidate_text(candidates: list[dict]) -> tuple[str, list[int]]:
    pages_used = [c["page"] for c in candidates]
    texts = [f"=== PAGE {c['page']} ===\n{c['combined']}" for c in candidates]
    return "\n\n".join(texts), pages_used


def extract_json_from_response(raw: str) -> dict:
    """Robustly extract JSON from LLM response, handling markdown fences and extra text."""
    if not raw or not raw.strip():
        raise ValueError("LLM returned an empty response.")

    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    raw = raw.strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object within the text
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON. Response starts with: {raw[:300]}")


def build_empty_result(currency: str, unit: str) -> dict:
    """Fallback result when LLM fails — returns all nulls so pipeline does not crash."""
    return {
        "extraction_metadata": {
            "currency": currency,
            "unit": unit,
            "fiscal_year_end": None,
            "years_detected": [],
            "source_context_notes": "Extraction failed — could not parse LLM response.",
        },
        "line_items": [
            {
                "canonical_name": item,
                "source_label": None,
                "values": {},
                "confidence": "LOW",
                "notes": "LLM extraction failed — please retry",
            }
            for item in CANONICAL_ITEMS
        ],
    }


def call_llm_extract(candidate_text: str, currency: str, unit: str) -> dict:
    client = Groq(api_key=GROQ_API_KEY)

    canonical_list = "\n".join(f"- {item}" for item in CANONICAL_ITEMS)

    system_prompt = (
        "You are a financial data extraction engine. "
        "You must respond with ONLY a valid JSON object. "
        "Do not include any markdown, code fences, explanation, or commentary. "
        "Your entire response must start with { and end with }."
    )

    user_prompt = f"""Extract income statement line items from the financial document text below.

Currency: {currency}
Unit: {unit}

Canonical line items to extract:
{canonical_list}

Document text:
---
{candidate_text[:10000]}
---

Return ONLY this JSON (no markdown, no extra text, start with {{):
{{
  "extraction_metadata": {{
    "currency": "{currency}",
    "unit": "{unit}",
    "fiscal_year_end": null,
    "years_detected": ["FY2023", "FY2024"],
    "source_context_notes": "brief description of document"
  }},
  "line_items": [
    {{
      "canonical_name": "Revenue",
      "source_label": "exact label from doc or null",
      "values": {{"FY2023": 12345.0, "FY2024": 13456.0}},
      "confidence": "HIGH",
      "notes": null
    }}
  ]
}}

Rules:
- Include ALL {len(CANONICAL_ITEMS)} canonical items in the line_items array
- Set values to null if not found — never estimate or calculate
- Use raw numbers as written (394328 not 394.328)
- Parenthetical (1234) = negative -1234
- confidence must be HIGH, MEDIUM, or LOW
"""

    try:
        message = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = message.choices[0].message.content
        print(f"[LLM RAW RESPONSE PREVIEW]: {raw[:300]}")
        return extract_json_from_response(raw)

    except Exception as e:
        print(f"[LLM ERROR] {type(e).__name__}: {e}")
        return build_empty_result(currency, unit)


def validate_arithmetic(line_items: list[dict], years: list[str]) -> list[str]:
    warnings = []

    def get_val(canonical: str, year: str) -> Optional[float]:
        for li in line_items:
            if li["canonical_name"] == canonical:
                v = li["values"].get(year)
                return float(v) if v is not None else None
        return None

    for year in years:
        revenue = get_val("Revenue", year)
        cogs = get_val("COGS", year)
        gross_profit = get_val("Gross Profit", year)

        if revenue is not None and cogs is not None and gross_profit is not None:
            expected = revenue - cogs
            if abs(revenue) > 0 and abs(expected - gross_profit) / abs(revenue) > 0.02:
                warnings.append(
                    f"{year}: Gross Profit mismatch — stated {gross_profit:,.0f}, computed {expected:,.0f}"
                )

    return warnings


def extract_financials(pdf_path: str, progress_callback: Callable = None) -> dict:
    def update(step, pct):
        if progress_callback:
            progress_callback(step, pct)

    update("Parsing PDF pages...", 20)
    pages = extract_all_text_and_tables(pdf_path)

    if not pages:
        raise ValueError("Could not extract any text from the PDF.")

    full_text = " ".join(p["combined"] for p in pages)

    update("Detecting currency and units...", 30)
    currency = detect_currency(full_text)
    unit = detect_unit(full_text)

    update("Identifying income statement sections...", 40)
    candidates = find_candidate_pages(pages)
    candidate_text, source_pages = build_candidate_text(candidates)

    update("Calling AI extraction engine...", 55)
    llm_result = call_llm_extract(candidate_text, currency, unit)

    metadata = llm_result.get("extraction_metadata", {})
    line_items = llm_result.get("line_items", [])
    years = metadata.get("years_detected", [])

    update("Normalizing line items...", 75)
    for li in line_items:
        li["match_method"] = "LLM"
        li["source_pages"] = source_pages

    update("Running arithmetic validation...", 82)
    warnings = validate_arithmetic(line_items, years)
    validation_status = "PASSED" if not warnings else "WARNINGS"

    metadata["currency"] = currency
    metadata["unit"] = unit
    metadata["source_pages"] = source_pages
    metadata["validation_status"] = validation_status
    metadata["warnings"] = warnings
    metadata["ocr_source"] = False
    metadata["total_pdf_pages"] = len(pages)

    return {
        "extraction_metadata": metadata,
        "years_detected": years,
        "line_items": line_items,
    }