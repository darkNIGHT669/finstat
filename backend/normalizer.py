# Canonical Income Statement line items — versioned schema v1.0
CANONICAL_ITEMS = [
    "Revenue",
    "COGS",
    "Gross Profit",
    "R&D Expenses",
    "SG&A Expenses",
    "Other Operating Expenses",
    "Total Operating Expenses",
    "Operating Income",
    "EBITDA",
    "Depreciation & Amortization",
    "Interest Expense",
    "Interest Income",
    "Other Income/Expense",
    "Income Before Tax",
    "Income Tax Expense",
    "Net Income",
    "Basic EPS",
    "Diluted EPS",
    "Basic Shares Outstanding",
    "Diluted Shares Outstanding",
]

# Alias map: source label variants → canonical name
ALIAS_MAP = {
    # Revenue
    "net revenue": "Revenue",
    "net revenues": "Revenue",
    "total revenue": "Revenue",
    "total revenues": "Revenue",
    "total net revenue": "Revenue",
    "total net revenues": "Revenue",
    "net sales": "Revenue",
    "total net sales": "Revenue",
    "sales": "Revenue",
    "revenues": "Revenue",
    "revenue from operations": "Revenue",
    "net operating revenues": "Revenue",
    # COGS
    "cost of goods sold": "COGS",
    "cost of sales": "COGS",
    "cost of revenue": "COGS",
    "cost of products": "COGS",
    "cost of services": "COGS",
    "cost of products sold": "COGS",
    "costs of revenues": "COGS",
    "cost of revenues": "COGS",
    # Gross Profit
    "gross profit": "Gross Profit",
    "gross margin": "Gross Profit",
    "gross income": "Gross Profit",
    # R&D
    "research and development": "R&D Expenses",
    "research & development": "R&D Expenses",
    "research and development expenses": "R&D Expenses",
    "r&d expenses": "R&D Expenses",
    "r&d": "R&D Expenses",
    "technology and development": "R&D Expenses",
    # SG&A
    "selling general and administrative": "SG&A Expenses",
    "selling, general and administrative": "SG&A Expenses",
    "selling, general and administrative expenses": "SG&A Expenses",
    "sg&a": "SG&A Expenses",
    "sga": "SG&A Expenses",
    "general and administrative": "SG&A Expenses",
    "marketing and sales": "SG&A Expenses",
    # Operating Expenses
    "total operating expenses": "Total Operating Expenses",
    "operating expenses": "Total Operating Expenses",
    "total costs and expenses": "Total Operating Expenses",
    # Operating Income
    "operating income": "Operating Income",
    "operating profit": "Operating Income",
    "income from operations": "Operating Income",
    "profit from operations": "Operating Income",
    "operating earnings": "Operating Income",
    "ebit": "Operating Income",
    "operating loss": "Operating Income",
    # EBITDA
    "ebitda": "EBITDA",
    "adjusted ebitda": "EBITDA",
    # D&A
    "depreciation and amortization": "Depreciation & Amortization",
    "depreciation & amortization": "Depreciation & Amortization",
    "depreciation": "Depreciation & Amortization",
    "amortization": "Depreciation & Amortization",
    # Interest
    "interest expense": "Interest Expense",
    "interest expenses": "Interest Expense",
    "finance costs": "Interest Expense",
    "interest income": "Interest Income",
    "interest and other income": "Interest Income",
    # Other
    "other income": "Other Income/Expense",
    "other expense": "Other Income/Expense",
    "other income (expense)": "Other Income/Expense",
    "other income, net": "Other Income/Expense",
    "non-operating income": "Other Income/Expense",
    # Pre-tax income
    "income before income taxes": "Income Before Tax",
    "income before taxes": "Income Before Tax",
    "pretax income": "Income Before Tax",
    "earnings before income taxes": "Income Before Tax",
    "income (loss) before income taxes": "Income Before Tax",
    # Tax
    "income tax expense": "Income Tax Expense",
    "provision for income taxes": "Income Tax Expense",
    "income tax": "Income Tax Expense",
    "income taxes": "Income Tax Expense",
    "tax expense": "Income Tax Expense",
    # Net Income
    "net income": "Net Income",
    "net earnings": "Net Income",
    "net profit": "Net Income",
    "net loss": "Net Income",
    "net income (loss)": "Net Income",
    "profit for the year": "Net Income",
    "profit after tax": "Net Income",
    # EPS
    "basic earnings per share": "Basic EPS",
    "basic eps": "Basic EPS",
    "basic net income per share": "Basic EPS",
    "diluted earnings per share": "Diluted EPS",
    "diluted eps": "Diluted EPS",
    "diluted net income per share": "Diluted EPS",
    # Shares
    "basic shares": "Basic Shares Outstanding",
    "basic weighted average shares": "Basic Shares Outstanding",
    "diluted shares": "Diluted Shares Outstanding",
    "diluted weighted average shares": "Diluted Shares Outstanding",
}


def normalize_label(label: str) -> str:
    """Map a source label to a canonical name. Returns None if no match found."""
    if not label:
        return None
    lower = label.lower().strip()
    # Direct alias lookup
    if lower in ALIAS_MAP:
        return ALIAS_MAP[lower]
    # Partial match
    for alias, canonical in ALIAS_MAP.items():
        if alias in lower or lower in alias:
            return canonical
    return None
