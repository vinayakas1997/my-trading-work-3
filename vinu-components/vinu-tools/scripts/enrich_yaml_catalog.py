"""Enrich YAML catalogs with descriptions, interpretations, and tunable params.

Reads existing YAML + formula strings, generates meaningful descriptions
and extracts numeric constants as tunable parameters.

Usage:
    python scripts/enrich_yaml_catalog.py
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

CATALOG_DIR = (
    Path(__file__).resolve().parent.parent
    / "vinu_tools" / "compute" / "formulas" / "catalog"
)

# ── Column name mapping ──────────────────────────────────────────────
COLUMN_NAMES = {
    "close": "close price",
    "open": "open price",
    "high": "high price",
    "low": "low price",
    "volume": "volume",
    "vwap": "VWAP",
    "returns": "returns",
    "ret": "returns",
    "amount": "trading amount",
}

# ── Operator-to-English mapping ─────────────────────────────────────
OP_DESC = {
    "rank": "cross-sectionally ranked",
    "ts_rank": "time-series ranked",
    "tsrank": "time-series ranked",
    "delta": "period-over-period change of",
    "delay": "lagged value of",
    "corr": "rolling correlation between",
    "ts_corr": "rolling correlation between",
    "cov": "rolling covariance between",
    "std": "rolling standard deviation of",
    "ts_std": "rolling standard deviation of",
    "sum": "rolling sum of",
    "ts_sum": "rolling sum of",
    "mean": "rolling mean of",
    "sma": "simple moving average of",
    "max": "rolling maximum of",
    "ts_max": "rolling maximum of",
    "min": "rolling minimum of",
    "ts_min": "rolling minimum of",
    "argmax": "time index of the maximum of",
    "ts_argmax": "time index of the maximum of",
    "argmin": "time index of the minimum of",
    "ts_argmin": "time index of the minimum of",
    "decay_linear": "linearly weighted moving average of",
    "decaylinear": "linearly weighted moving average of",
    "sign": "sign (directional indicator) of",
    "abs": "absolute value of",
    "log": "log of",
    "scale": "normalized",
    "signed_power": "signed power transformation of",
}

# ── Negation descriptions ─────────────────────────────────────────────
NEGATE_DESC = {
    "reversal": "making this a contrarian signal — high values predict mean reversion downward.",
    "momentum": "reversing the trend signal — high values may indicate weakening momentum.",
    "volatility": "inverting the volatility reading — high values suggest calm, low values suggest stress.",
    "volume": "inverting volume — high values occur when volume declines.",
}

# ── THEME-BASED DESCRIPTION PATTERNS ──────────────────────────────────
THEME_DESCRIPTIONS = {
    "reversal": "Detects potential price reversals by identifying overextended moves or divergences.",
    "momentum": "Measures trend strength and directional price movement over a lookback window.",
    "volatility": "Quantifies price variability and expansion/contraction of trading ranges.",
    "volume": "Analyzes trading volume patterns and their relationship with price movements.",
    "value": "Compares price to fundamental value proxies to identify over/underpriced assets.",
    "growth": "Captures changes in earnings, revenue, or other fundamental growth metrics.",
    "quality": "Measures profitability, stability, or other quality characteristics.",
    "size": "Relates to market capitalization or dollar-volume based effects.",
    "liquidity": "Assesses trading activity, bid-ask spreads, or ease of execution.",
    "sentiment": "Captures market mood through price action patterns or positioning data.",
    "seasonality": "Exploits calendar-based patterns or periodic market behaviors.",
    "microstructure": "Analyzes order flow, tick-level patterns, or intraday price dynamics.",
    "other": "Specialized alpha with unique construction not fitting standard categories.",
}

THEME_USE_CASES = {
    "reversal": "mean_reversion, contrarian_trading, exhaustion_detection",
    "momentum": "trend_following, breakout_trading, factor_investing",
    "volatility": "volatility_breakout, options_trading, risk_management",
    "volume": "volume_analysis, liquidity_screening, accumulation_distribution",
    "value": "value_investing, fundamental_screening, cross_sectional_ranking",
    "growth": "growth_investing, earnings_momentum, fundamental_analysis",
    "quality": "quality_screening, defensive_investing, fundamental_analysis",
    "size": "size_factor, small_cap_trading, market_neutral",
    "liquidity": "liquidity_screening, execution_analysis, market_making",
    "sentiment": "sentiment_analysis, behavioral_finance, event_driven",
    "seasonality": "seasonal_trading, calendar_effects, monthly_patterns",
    "microstructure": "high_frequency, order_flow, intraday_trading",
    "other": "alpha_research, factor_discovery, signal_generation",
}

# ── Formula node type classification ──────────────────────────────────

FORMULA_CONCEPTS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"CORR.*RANK.*DELTA.*LOG.*VOLUME.*RANK.*CLOSE.*OPEN.*OPEN"), "volume_price_divergence", "correlation"),
    (re.compile(r"CORR.*RANK.*VOLUME.*RANK.*(CLOSE|HIGH|LOW|OPEN)"), "volume_price_correlation", "correlation"),
    (re.compile(r"CORR.*(CLOSE|OPEN|HIGH|LOW|VOLUME).*(CLOSE|OPEN|HIGH|LOW|VOLUME)"), "cross_asset_correlation", "correlation"),
    (re.compile(r"RANK.*DELTA.*LOG.*VOLUME"), "volume_change", "rank"),
    (re.compile(r"CLOSE.*LOW.*HIGH.*LOW.*CLOSE"), "close_position", "position"),
    (re.compile(r"CLOSE.*OPEN.*OPEN"), "intraday_return", "return"),
    (re.compile(r"HIGH.*LOW.*CLOSE.*LOW"), "price_range_position", "position"),
    (re.compile(r"SMA.*CLOSE.*VOLUME"), "volume_weighted_price", "average"),
    (re.compile(r"STD.*RETURNS|STD.*CLOSE"), "volatility", "volatility"),
    (re.compile(r"MAX.*HIGH|MIN.*LOW"), "price_extremes", "extreme"),
    (re.compile(r"SIGN.*DELTA"), "directional_change", "direction"),
    (re.compile(r"DECAYLINEAR"), "weighted_average", "average"),
    (re.compile(r"SUM.*RETURNS|SUM.*CLOSE"), "cumulative_return", "cumulative"),
    (re.compile(r"RANK.*SUM.*"), "ranked_cumulative", "rank"),
    (re.compile(r"TSRANK.*CORR"), "ranked_correlation", "correlation"),
]


def classify_formula_concept(formula: str) -> list[tuple[str, str]]:
    """Classify a formula into high-level concepts."""
    concepts = []
    for pattern, concept_name, _ in FORMULA_CONCEPTS:
        if pattern.search(formula.upper()) or pattern.search(formula):
            concepts.append(concept_name)
    return concepts


# ── PARAM EXTRACTION ──────────────────────────────────────────────────

PARAM_PATTERNS = [
    (r"(?:ts_|rolling_|trailing_)?(?:mean|avg|std|corr|cov|sum|max|min|argmax|argmin|rank|mad|quantile)\([^,]+,\s*(\d+)\)", "window", 60),
    (r"(?:ts_|rolling_|trailing_)?(?:mean|avg|std|corr|cov|sum|max|min|argmax|argmin|rank|mad|quantile)\([^,]+,\s*[^,]+,\s*(\d+)\)", "window", 60),
    (r"delta\([^,]+,\s*(\d+)\)", "lag", 1),
    (r"decay_linear\([^,]+,\s*(\d+)\)", "decay", 10),
    (r"(?:delay|lag|ref|shift)\([^,]+,\s*(\d+)\)", "lag", 1),
    (r"signed_power\([^,]+,\s*([\d.]+)\)", "power", 2.0),
    (r"(?:quantile|percentile)\([^,]+,\s*([\d.]+)\)", "quantile", 0.5),
]


def extract_numeric_params(formula: str, decay_horizon: int) -> dict:
    params = {}
    if not formula:
        return params
    for pattern, default_name, default_value in PARAM_PATTERNS:
        matches = re.findall(pattern, formula, re.IGNORECASE)
        for m in matches:
            val = int(m) if float(m).is_integer() else float(m)
            name = default_name
            suffix = 1
            while name in params:
                suffix += 1
                name = f"{default_name}_{suffix}"
            lo = max(1, val // 2)
            hi = min(252, val * 4)
            params[name] = {
                "default": val,
                "range": [lo, hi],
                "description": f"{default_name.replace('_', ' ')} parameter (original: {val})"
            }
    return params


# ── IMPROVED DESCRIPTION GENERATOR ────────────────────────────────────

def _col_readable(col: str) -> str:
    return COLUMN_NAMES.get(col.lower(), col)


def _parse_nested_formula(formula: str, columns: list | None = None) -> list[str]:
    """Extract meaningful computation steps from formula."""
    steps = []
    col_str = ", ".join(_col_readable(c) for c in columns) if columns else "price"

    upper = formula.upper()

    # Correlation patterns
    corr_match = re.search(r"(?:CORR|TS_CORR|corr|ts_corr)\((.+?),\s*(.+?),\s*(\d+)\)", formula)
    if corr_match:
        x, y, n = corr_match.group(1), corr_match.group(2), corr_match.group(3)
        x_desc = _simplify_expr(x)
        y_desc = _simplify_expr(y)
        steps.append(f"{n}-period rolling correlation between {x_desc} and {y_desc}")

    # Delta patterns
    delta_matches = re.findall(r"DELTA\((.+?),\s*(\d+)\)", upper)
    for expr, n in delta_matches:
        steps.append(f"{n}-period change in {_simplify_expr(expr)}")

    # Standard deviation
    std_matches = re.findall(r"STD\((.+?),\s*(\d+)\)", upper)
    for expr, n in std_matches:
        steps.append(f"{n}-period volatility of {_simplify_expr(expr)}")

    # Moving average
    sma_matches = re.findall(r"(?:SMA|MEAN|sma|mean)\((.+?),\s*(\d+)\)", formula)
    for expr, n in sma_matches:
        steps.append(f"{n}-period average of {_simplify_expr(expr)}")

    # Rolling sum
    sum_matches = re.findall(r"(?:SUM|sum)\((.+?),\s*(\d+)\)", formula)
    for expr, n in sum_matches:
        steps.append(f"{n}-period sum of {_simplify_expr(expr)}")

    # Decay linear
    decay_matches = re.findall(r"(?:DECAYLINEAR|decay_linear)\((.+?),\s*(\d+)\)", upper)
    for expr, n in decay_matches:
        steps.append(f"{n}-period linearly weighted average of {_simplify_expr(expr)}")

    # Max/Min patterns
    maxmin_matches = re.findall(r"(?:TS_MAX|TS_MIN)\((.+?),\s*(\d+)\)", upper)
    for expr, n in maxmin_matches:
        steps.append(f"{n}-period extremum of {_simplify_expr(expr)}")

    # Close position in range: (CLOSE - LOW) / (HIGH - LOW) or similar
    if not any("ratio" in s.lower() for s in steps):
        range_pos = re.search(r"\((.+?)\s*-\s*(LOW|L)\s*\)\s*/\s*\((HIGH|H)\s*-\s*(LOW|L)\s*\)", upper)
        if range_pos:
            steps.append(f"close price position within high-low range")

    # Arithmetic expressions involving ratios
    ratio_in_formula = re.findall(r"\(.+?\)\s*/\s*\(.+?\)", formula)
    for m in ratio_in_formula:
        ratio_desc = _simplify_expr(m)
        if ratio_desc and ratio_desc not in [s.lower().strip(".") for s in steps]:
            steps.append(ratio_desc)

    # Cross-sectional rank pattern (not inside another function)
    cs_rank_count = len(re.findall(r"\bRANK\(", upper))
    if cs_rank_count >= 2:
        steps.append("cross-sectional rank applied to normalize output across assets")

    if not steps:
        fallback = _simplify_expr(formula)
        if fallback and fallback not in ("see body", "", "nan", "none"):
            steps.append(fallback)
        elif col_str:
            steps.append(f"a transformation of {col_str} data")
        else:
            steps.append("a mathematical transformation")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in steps:
        norm = s.lower().strip().rstrip(".")
        if norm not in seen:
            seen.add(norm)
            unique.append(s)
    return unique


def _simplify_expr(expr: str) -> str:
    """Convert a formula expression to readable English."""
    e = expr.strip()

    # Handle conditional operator (condition)?true_value:false_value
    cond_match = re.search(r"\((.+?)\)\?\(?(.+?)\)?\:(.+?)(?:,|$|\))", e)
    if cond_match:
        condition = _simplify_expr(cond_match.group(1))
        true_val = _simplify_expr(cond_match.group(2))
        false_val = _simplify_expr(cond_match.group(3))
        return f"conditional {true_val} if {condition}, else {false_val}"

    # Handle power with ^
    power_match = re.search(r"\((.+?)\)\^(\d+)", e)
    if power_match:
        base = _simplify_expr(power_match.group(1))
        exp = power_match.group(2)
        return f"{base} raised to power {exp}"

    # Handle RANK(...)
    rank_match = re.search(r"RANK\((.+)\)", e.upper())
    if rank_match:
        inner = rank_match.group(1)
        inner_desc = _simplify_expr(inner)
        return f"cross-sectional rank of {inner_desc}"

    # Handle LOG(...)
    log_match = re.search(r"LOG\((.+)\)", e.upper())
    if log_match:
        return f"log({log_match.group(1).lower()})"

    # Handle DELTA(...)
    delta_match = re.search(r"DELTA\((.+),\s*(\d+)\)", e.upper())
    if delta_match:
        inner = delta_match.group(1)
        n = delta_match.group(2)
        return f"{n}-period change of {_simplify_expr(inner)}"

    # Handle SIGN(...)
    sign_match = re.search(r"SIGN\((.+)\)", e.upper())
    if sign_match:
        return f"sign of {_simplify_expr(sign_match.group(1))}"

    # Handle ABS(...)
    abs_match = re.search(r"ABS\((.+)\)", e.upper())
    if abs_match:
        return f"absolute value of {_simplify_expr(abs_match.group(1))}"

    # Handle TS_MAX / TS_MIN
    tsx_match = re.search(r"(TS_MAX|TS_MIN|MAX|MIN)\((.+),\s*(\d+)\)", e.upper())
    if tsx_match:
        func = tsx_match.group(1).lower()
        inner = _simplify_expr(tsx_match.group(2))
        n = tsx_match.group(3)
        if "max" in func:
            return f"{n}-period maximum of {inner}"
        return f"{n}-period minimum of {inner}"

    # Handle MEAN(...) / SMA(...)
    avg_match = re.search(r"(?:SMA|MEAN|AVG)\((.+),\s*(\d+)\)", e.upper())
    if avg_match:
        return f"{avg_match.group(2)}-period average of {_simplify_expr(avg_match.group(1))}"

    # Handle close position in range: (CLOSE - LOW) / (HIGH - LOW)
    range_pos = re.search(r"\((.+?)\s*-\s*(.+?)\)\s*/\s*\((.+?)\s*-\s*(.+?)\)", e.upper())
    if range_pos:
        num_top = range_pos.group(1).strip()
        num_bot = range_pos.group(2).strip()
        den_top = range_pos.group(3).strip()
        den_bot = range_pos.group(4).strip()
        # Common pattern: close position in high-low range
        if (num_bot == "LOW" and den_top == "HIGH" and den_bot == "LOW") or \
           (num_bot == "L" and den_top == "H" and den_bot == "L"):
            return f"close price position within high-low range"
        if num_bot == "OPEN":
            return f"{_simplify_expr(num_top)} minus open relative to {_simplify_expr(den_top)} minus {_simplify_expr(den_bot)}"
        return f"({_simplify_expr(num_top)} minus {_simplify_expr(num_bot)}) divided by ({_simplify_expr(den_top)} minus {_simplify_expr(den_bot)})"

    # Handle simple ratio A / B
    simple_ratio = re.search(r"^\(?(.+?)\)?\s*/\s*\(?(.+?)\)?$", e.upper())
    if simple_ratio:
        num = _simplify_expr(simple_ratio.group(1))
        den = _simplify_expr(simple_ratio.group(2))
        return f"{num} divided by {den}"

    # Handle product A * B
    prod_match = re.search(r"\(?(.+?)\)?\s*\*\s*\(?(.+?)\)?$", e.upper())
    if prod_match and "*" in e and "/" not in e:
        a = _simplify_expr(prod_match.group(1))
        b = _simplify_expr(prod_match.group(2))
        return f"{a} multiplied by {b}"

    # Simple column references — group meaningfully
    col_refs = re.findall(r"\b(CLOSE|OPEN|HIGH|LOW|VOLUME|VWAP|RETURNS|AMOUNT|RET)\b", e.upper())
    if col_refs:
        cols = [_col_readable(c) for c in col_refs]
        if len(cols) == 1:
            return cols[0]
        ops = re.findall(r"[-+*/]", e)
        # If it's a simple comparison of two columns
        if len(cols) == 2 and ops == ["-"]:
            return f"{cols[0]} relative to {cols[1]}"
        if len(cols) == 2:
            return f"{cols[0]} and {cols[1]}"
        # Multi-column: group by type
        price_cols = [c for c in cols if "price" in c]
        vol_cols = [c for c in cols if "volume" in c]
        if price_cols and vol_cols:
            return f"{', '.join(price_cols)} and {', '.join(vol_cols)}"
        return " and ".join(cols) if len(cols) <= 3 else ", ".join(cols)

    # Handle negation
    if e.startswith("-"):
        inner = _simplify_expr(e.lstrip("-"))
        return f"negative {inner}" if inner else "negated value"

    # Handle (A + B)
    add_match = re.search(r"\((.+?)\s*\+\s*(.+?)\)", e.upper())
    if add_match:
        a = _simplify_expr(add_match.group(1))
        b = _simplify_expr(add_match.group(2))
        return f"{a} plus {b}"

    # Handle (A - B)
    sub_match = re.search(r"\((.+?)\s*-\s*(.+?)\)", e.upper())
    if sub_match:
        a = _simplify_expr(sub_match.group(1))
        b = _simplify_expr(sub_match.group(2))
        return f"{a} minus {b}"

    return e.lower().replace("_", " ").strip()


def _format_n(n: int) -> str:
    if n == 1:
        return "1-period"
    return f"{n}-period"


def _has_volume_in_formula(formula: str) -> bool:
    return bool(re.search(r'\b(volume|VOLUME|vwap|VWAP|amount|AMOUNT)\b', formula))

def _has_corr_in_formula(formula: str) -> bool:
    return bool(re.search(r'\b(corr|CORR|ts_corr|TS_CORR)\b', formula))

def _has_delta_in_formula(formula: str) -> bool:
    return bool(re.search(r'\b(delta|DELTA)\b', formula))

def generate_description(factor_id: str, theme: list, formula: str, columns: list, decay: int) -> str:
    """Generate a meaningful description based on formula structure."""
    theme_lower = [t.lower() for t in theme] if isinstance(theme, list) else [str(theme).lower()]
    has_neg = formula.strip().startswith("-") or formula.strip().startswith("(-")
    concepts = classify_formula_concept(formula)

    # Parse meaningful computation steps
    steps = _parse_nested_formula(formula, columns)

    cols_used = [c for c in ["close", "open", "high", "low", "volume", "vwap", "returns"] if c in columns]
    col_str = ", ".join(_col_readable(c) for c in cols_used) if cols_used else "price"

    # Detect formula category for better opening
    has_volume = _has_volume_in_formula(formula)
    has_corr = _has_corr_in_formula(formula)
    has_delta = _has_delta_in_formula(formula)
    has_range_position = "close" in formula.lower() and "low" in formula.lower() and "high" in formula.lower()
    has_ratio = "rank" in formula.lower()
    has_return = "ret" in formula.lower() or "return" in formula.lower()

    # Build description
    parts = []

    # Sentence 1: What it computes — use formula-specific opening when possible
    if has_corr and has_volume:
        theme_lead = "Measures the correlation between trading activity and price movement."
    elif has_corr and not has_volume:
        theme_lead = "Quantifies the co-movement between market variables over a rolling window."
    elif has_range_position and "rank" in formula:
        theme_lead = "Ranks securities by their closing price position within the recent trading range."
    elif has_delta and has_ratio:
        theme_lead = "Captures momentum-adjusted price changes relative to market activity."
    elif has_neg and "rank" in formula:
        theme_lead = THEME_DESCRIPTIONS.get("reversal", "Identifies securities with potential for mean reversion.")
    else:
        theme_lead = THEME_DESCRIPTIONS.get(theme_lower[0], "Alpha factor computed from price and volume data.")
    parts.append(theme_lead)

    # Sentence 2: Compute logic
    if steps:
        prefix = "Inverted, " if has_neg else ""
        step_desc = steps[0]
        if len(steps) > 1:
            step_desc += f", with further adjustment via {', '.join(steps[1:])}"
        parts.append(f"It computes the {prefix}{step_desc}.")
    else:
        parts.append(f"Computed from {col_str} data{' over a ' + str(decay) + '-period lookback' if decay else ''}.")

    # Sentence 3: Formula context
    if has_neg:
        parts.append("Negated to create an inverse signal — high raw values predict downward moves.")
    elif decay:
        parts.append(f"The signal uses a {decay}-period estimation window.")

    # Sentence 4: Concrete interpretation based on structure
    if "volume_price_divergence" in concepts:
        parts.append("When volume rises but price stalls, correlation drops — signaling potential reversal or exhaustion.")
    elif "volume_price_correlation" in concepts:
        parts.append("High correlation = volume confirms price trend. Low correlation = divergence warns of reversal.")
    elif "close_position" in concepts or has_range_position:
        parts.append("Values near 1 = close at range top (strength). Values near 0 = close at range bottom (weakness). Cross-sectional rank makes this relative across assets.")
    elif "intraday_return" in concepts:
        parts.append("Positive = bullish intraday session. Negative = bearish intraday session.")
    elif "volatility" in concepts:
        parts.append("Rises during market stress and volatile periods. Falls during calm, trending markets.")
    elif "price_range_position" in concepts:
        parts.append("Values near 1 = price near high of recent range. Values near 0 = price near recent low.")
    elif has_corr and "volume" in formula.lower():
        parts.append("Useful for detecting volume-confirmed breakouts (high corr) or distribution days (low corr).")

    # Sentence 5: Data context
    parts.append(f"Uses {col_str} data.")

    # Sentence 6: Use case context
    if theme_lower:
        use_cases = THEME_USE_CASES.get(theme_lower[0], "")
        if use_cases and "alpha_research" not in use_cases:
            first_use = use_cases.split(",")[0].replace("_", " ")
            parts.append(f"Best suited for {first_use}.")

    return " ".join(parts)


def generate_interpretation(factor_id: str, formula: str, theme: list, decay: int) -> str:
    """Generate interpretation guidance."""
    theme_lower = [t.lower() for t in theme] if isinstance(theme, list) else [str(theme).lower()]
    has_rank = "rank" in formula.lower()
    has_neg = formula.strip().startswith("-") or formula.strip().startswith("(-")
    has_corr = "corr" in formula.lower()

    parts = []
    if has_corr:
        if has_neg:
            parts.append("Range [-1, 1]. High positive = trend continuation (sell). High negative = volume-price divergence, reversal expected (buy).")
        else:
            parts.append("Range [-1, 1]. High positive = factors move together. High negative = factors diverge.")
    elif has_rank:
        parts.append("Cross-sectional rank [0, 1]. Values near 1 = strong factor exposure. Values near 0 = weak or negative exposure.")
    else:
        parts.append("Higher values indicate stronger factor exposure.")

    if has_neg and not has_corr:
        parts.append("Because the signal is negated, high raw values predict downward moves.")

    theme_notes = []
    if "reversal" in theme_lower:
        theme_notes.append("Best used near price extremes for contrarian entries")
    if "momentum" in theme_lower:
        theme_notes.append("Works best in trending markets")
    if "volatility" in theme_lower:
        theme_notes.append("Rises during market stress, falls during calm periods")
    if "volume" in theme_lower:
        theme_notes.append("Volume spikes indicate institutional activity or unusual interest")
    if "liquidity" in theme_lower:
        theme_notes.append("Lower values may indicate illiquid stocks")
    if "momentum" in theme_lower and "reversal" in theme_lower:
        theme_notes.append("Combines trend and mean-reversion — use with caution near turning points")

    if theme_notes:
        parts.append(". ".join(theme_notes))

    return ". ".join(parts) if parts else "Higher values = stronger signal. Lower values = weaker signal."


def generate_when_to_use(theme: list) -> str:
    return ", ".join(set(
        THEME_USE_CASES.get(str(t).lower(), "alpha_research")
        for t in (theme if isinstance(theme, list) else [theme])
    ))


# ── MAIN ──────────────────────────────────────────────────────────────

HAND_ENRICHED_IDS = {
    "gtja191_001", "gtja191_002", "gtja191_003", "gtja191_004", "gtja191_005",
}

THEME_CACHE = {}


def get_theme_str(theme_val) -> list:
    key = str(theme_val)
    if key not in THEME_CACHE:
        if isinstance(theme_val, list):
            THEME_CACHE[key] = theme_val
        else:
            THEME_CACHE[key] = [theme_val]
    return THEME_CACHE[key]


def main():
    for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
        print(f"Enriching {yaml_path.name}...")
        with open(yaml_path, encoding="utf-8") as f:
            catalog = yaml.safe_load(f) or {}

        enriched = 0
        for factor_id, entry in catalog.items():
            theme = entry.get("theme", ["other"])
            formula = entry.get("formula", "")
            columns = entry.get("columns_required", ["close"])
            decay = entry.get("decay_horizon", 0)

            if factor_id in HAND_ENRICHED_IDS:
                continue

            # Generate fields
            entry["description"] = generate_description(factor_id, theme, formula, columns, decay)
            entry["interpretation"] = generate_interpretation(factor_id, formula, theme, decay)
            entry["when_to_use"] = generate_when_to_use(theme)

            # Extract params (don't overwrite if params already exist)
            if not entry.get("params") or entry["params"] == {}:
                extracted = extract_numeric_params(formula, decay)
                if extracted:
                    entry["params"] = extracted

            enriched += 1

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(catalog, f, default_flow_style=None, sort_keys=False, allow_unicode=True, width=120)

        print(f"  → {enriched} factors enriched in {yaml_path.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
