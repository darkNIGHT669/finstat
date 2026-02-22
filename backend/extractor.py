import re
import json
import os
from typing import Callable, Optional
import pdfplumber
import anthropic

from normalizer import normalize_label, CANONICAL_ITEMS

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

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
    # Normalize dashes and spaces
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    # Remove excessive whitespace lines
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
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
            # Convert tables to text representation
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
        # Lower threshold if nothing found
        best = max(scored, key=lambda x: x[1])
        candidates = [best] if best[1] > 0 else scored[:5]
    # Sort by score descending, take top 8 pages
    candidates.sort(key=lambda x: x[1], reverse=True)
    top = [p for p, _ in candidates[:8]]
    # Re-sort by page number
    top.sort(key=lambda p: p["page"])
    return top


def build_candidate_text(candidates: list[dict]) -> tuple[str, list[int]]:
    pages_used = [c["page"] for c in candidates]
    texts = []
    for c in candidates:
        texts.append(f"=== PAGE {c['page']} ===\n{c['combined']}")
    return "\n\n".join(texts), pages_used


def call_llm_extract(candidate_text: str, currency: str, unit: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    canonical_list = "\n".join(f"- {item}" for item in CANONICAL_ITEMS)

    system_prompt = """You are a financial data extraction engine for an internal analyst research portal.
Your job is to extract income statement line items from raw financial document text.

STRICT RULES — violating these is a critical failure:
1. Extract ONLY values explicitly present in the document text. NEVER infer, calculate, or estimate.
2. If a line item is NOT in the text, set its values to null — never to 0 or any estimate.
3. Extract the exact numeric value as written (before any unit scaling). Handle parenthetical negatives: (1,234) = -1234.
4. Identify ALL fiscal years present as separate columns.
5. Return ONLY valid JSON. No markdown, no commentary, no explanation outside JSON.
6. For confidence: HIGH = exact match + clear value, MEDIUM = fuzzy match or ambiguous, LOW = unclear."""

    user_prompt = f"""Extract income statement data from the following financial document text.

Document context:
- Detected currency: {currency}
- Detected unit: {unit}

Canonical line items to extract (map source labels to these):
{canonical_list}

Document text:
---
{candidate_text[:12000]}
---

Return a JSON object with this exact structure:
{{
  "extraction_metadata": {{
    "currency": "{currency}",
    "unit": "{unit}",
    "fiscal_year_end": "<month or null>",
    "years_detected": ["FY2023", "FY2024"],
    "source_context_notes": "<brief note about document structure>"
  }},
  "line_items": [
    {{
      "canonical_name": "<from canonical list above>",
      "source_label": "<exact label as written in document, or null if inferred>",
      "values": {{"FY2023": 12345.0, "FY2024": 13456.0}},
      "confidence": "HIGH|MEDIUM|LOW",
      "notes": "<any important caveats, or null>"
    }}
  ]
}}

Include ALL canonical line items in the response — set values to null for those not found.
Numbers should be raw numeric values as written in the document (e.g., 394328 not 394.328).
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code blocks if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


def validate_arithmetic(line_items: list[dict], years: list[str]) -> list[str]:
    warnings = []

    def get_val(canonical: str, year: str) -> Optional[float]:
        for li in line_items:
            if li["canonical_name"] == canonical:
                return li["values"].get(year)
        return None

    for year in years:
        revenue = get_val("Revenue", year)
        cogs = get_val("COGS", year)
        gross_profit = get_val("Gross Profit", year)
        operating_income = get_val("Operating Income", year)
        net_income = get_val("Net Income", year)

        if revenue is not None and cogs is not None and gross_profit is not None:
            expected = revenue - cogs
            if abs(expected - gross_profit) / (abs(revenue) + 1) > 0.02:
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

    # Merge/normalize
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
