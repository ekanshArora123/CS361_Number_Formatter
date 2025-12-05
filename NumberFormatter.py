from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# -------------------------------
# Configuration (easy to extend)
# -------------------------------
# Adding a new locale = add one entry here.
LOCALE_CONFIG = {
    "US": {
        "decimal_sep": ".",
        "thousands_sep": ",",
        "currency_symbol": "$",
        "currency_symbol_position": "before",  # "before" or "after"
        "currency_symbol_space": False,
    },
    "EU": {
        "decimal_sep": ",",
        "thousands_sep": ".",
        "currency_symbol": "€",
        "currency_symbol_position": "after",   # "before" or "after"
        "currency_symbol_space": True,
    },
    # Example: adding "UK" only requires adding this block.
    "UK": {
        "decimal_sep": ".",
        "thousands_sep": ",",
        "currency_symbol": "£",
        "currency_symbol_position": "before",
        "currency_symbol_space": False,
    },
}


# -------------------------------
# Formatting helpers
# -------------------------------
def group_thousands(integer_part: str, sep: str) -> str:
    """Apply thousands grouping to a string of digits."""
    if len(integer_part) <= 3:
        return integer_part

    rev = integer_part[::-1]
    groups = [rev[i:i+3] for i in range(0, len(rev), 3)]
    return sep.join(g[::-1] for g in groups[::-1])


def format_plain(value: float, locale_cfg: dict, decimals: int, grouping: bool) -> str:
    """Format a number with optional grouping and locale separators."""
    sign = "-" if value < 0 else ""
    abs_val = abs(value)

    fmt = f"{{:.{decimals}f}}"
    number_str = fmt.format(abs_val)  # e.g. "1234.50" or "42.0"
    if "." in number_str:
        int_part, frac_part = number_str.split(".")
    else:
        int_part, frac_part = number_str, ""

    if grouping:
        int_part = group_thousands(int_part, locale_cfg["thousands_sep"])

    if decimals > 0:
        result = int_part + locale_cfg["decimal_sep"] + frac_part
    else:
        result = int_part

    return sign + result


def format_currency(value: float, locale_cfg: dict, decimals: int) -> str:
    """Format a number as currency according to locale config."""
    base = format_plain(value, locale_cfg, decimals, grouping=True)
    sign = ""
    if base.startswith("-"):
        sign = "-"
        base = base[1:]

    symbol = locale_cfg["currency_symbol"]
    before = locale_cfg["currency_symbol_position"] == "before"
    space = " " if locale_cfg["currency_symbol_space"] else ""

    if before:
        formatted_number = f"{symbol}{space}{base}"
    else:
        formatted_number = f"{base}{space}{symbol}"

    return sign + formatted_number


def format_scientific(value: float, locale_cfg: dict, digits: int = 3) -> str:
    """Format a number in scientific notation. Decimal separator follows locale."""
    # Use standard scientific notation with '.' then swap if needed
    fmt = f"{{:.{digits}e}}"
    raw = fmt.format(value)  # e.g. "1.234e+03"
    decimal_sep = locale_cfg["decimal_sep"]
    if decimal_sep != ".":
        # Replace the first '.' before the exponent, not the one in 'e+03'
        mantissa, exp = raw.split("e")
        mantissa = mantissa.replace(".", decimal_sep, 1)
        return mantissa + "e" + exp
    return raw


def format_number(value: float, locale: str = "US",
                  style: str = "currency", decimals: int | None = None) -> str:
    """Main formatting function."""
    locale_cfg = LOCALE_CONFIG.get(locale)
    if not locale_cfg:
        raise ValueError(f"Unknown locale: {locale}")

    style = style.lower()

    if style == "currency":
        if decimals is None:
            decimals = 2
        return format_currency(value, locale_cfg, decimals)

    elif style in ("comma", "grouped"):
        # Just grouping and integer or fixed decimals
        if decimals is None:
            decimals = 0
        return format_plain(value, locale_cfg, decimals, grouping=True)

    elif style in ("round", "rounded"):
        # No grouping, just rounding to given decimals
        if decimals is None:
            decimals = 0
        return format_plain(value, locale_cfg, decimals, grouping=False)

    elif style in ("sci", "scientific"):
        return format_scientific(value, locale_cfg)

    else:
        raise ValueError(f"Unknown style: {style}")


# -------------------------------
# Flask endpoint
# -------------------------------
@app.route("/format", methods=["GET", "POST"])
def format_endpoint():
    """
    Format a number according to locale and style.

    GET example:
      /format?value=1234.56&locale=US&style=currency&decimals=2

    POST example (JSON body):
      {
        "value": 1234.56,
        "locale": "EU",
        "style": "currency",
        "decimals": 2
      }
    """
    if request.method == "GET":
        value = request.args.get("value")
        locale = request.args.get("locale", "US")
        style = request.args.get("style", "currency")
        decimals = request.args.get("decimals", default=None, type=int)
    else:  # POST
        data = request.get_json(silent=True) or {}
        value = data.get("value")
        locale = data.get("locale", "US")
        style = data.get("style", "currency")
        decimals = data.get("decimals")

        # Allow decimals passed as string or number
        if isinstance(decimals, str):
            try:
                decimals = int(decimals)
            except ValueError:
                return jsonify({"error": "decimals must be an integer"}), 400

    if value is None:
        return jsonify({"error": "value is required"}), 400

    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be numeric"}), 400

    try:
        formatted = format_number(value, locale=locale, style=style, decimals=decimals)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "input": {
            "value": value,
            "locale": locale,
            "style": style,
            "decimals": decimals,
        },
        "formatted": formatted
    })


@app.route("/locales", methods=["GET"])
def list_locales():
    """Simple helper to show available locales."""
    return jsonify({
        "locales": list(LOCALE_CONFIG.keys())
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=False)
