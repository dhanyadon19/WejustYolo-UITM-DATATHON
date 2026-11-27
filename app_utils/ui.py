"""Shared look and feel: one accent colour, muted greys, validated categorical slots for the
three fix categories, chart styling, captions and source footers."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# --- palette (reference palette, light mode; validated with the dataviz validator) ---
ACCENT = "#2a78d6"          # the one accent colour
INK = "#0b0b0b"
INK_2 = "#52514e"            # secondary text
MUTED = "#898781"            # axis labels, de-emphasised marks
MUTED_LIGHT = "#c3c2b7"      # context marks, baseline
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

# Fix categories: deep blue / orange / lighter green, chosen for strong lightness contrast and
# validated all-pairs (dataviz validator: lightness, chroma, CVD >= 10, normal-vision >= 25).
# Fixed mapping, never cycled. The green is below 3:1 on light, so it always appears with labels,
# tooltips or tables.
FIX_COLOURS = {"tower": "#1c5cab", "satellite": "#eb6834", "takeup_gap": "#58b98c"}
FIX_LABELS = {"tower": "Tower", "satellite": "Satellite", "takeup_gap": "Take-up gap (fixed network likely nearby)",
              "none (take-up gap only)": "Take-up gap only"}
FIX_COLOURS["none (take-up gap only)"] = FIX_COLOURS["takeup_gap"]
# Sequential (one hue, light -> dark) ramp around the take-up green, for shares binned in equal steps of 0-100%.
# Validated with the dataviz validator (--ordinal, light surface): monotone lightness, visible steps, light end 2.08:1.
TAKEUP_RAMP = ["#74c19b", "#4fae82", "#2f8f64", "#1f6f4b", "#134f35"]

# Settlement types (config/settlement_types.yaml), legend order A, B, E, D, C (+ U if any data is missing).
# A/B/D reuse the take-up / tower / satellite colours. Validated all-pairs on light (dataviz validator: lightness,
# chroma, CVD >= 9.6, normal-vision >= 16.3). Green and gold are below 3:1 on light and the set is outside the
# dark-surface lightness band, so dots always carry a white ring, a legend, tooltips and a table view.
TYPE_ORDER = ["A", "B", "E", "D", "C", "U"]
TYPE_COLOURS = {"A": "#58b98c", "B": "#1c5cab", "E": "#9085e9", "D": "#eb6834", "C": "#d4b000", "U": "#c3c2b7"}
SCREENING = "candidate technologies (screening)"


def cost_basis_short(basis) -> str:
    """'FWA retail plan per household, five-year (costs.yaml)' -> 'FWA retail plan per household' (acronyms kept)."""
    b = str(basis).split(",")[0]
    return b if b[:2].isupper() or b[:1].isdigit() else b[:1].lower() + b[1:]
NOT_COSTED = "not costed (no public cost source)"

# MOE school-type prefixes -> the usual short forms (longest first)
_SCHOOL_PREFIX = [("SEKOLAH JENIS KEBANGSAAN (CINA)", "SJK(C)"), ("SEKOLAH JENIS KEBANGSAAN (TAMIL)", "SJK(T)"),
                  ("SEKOLAH JENIS KEBANGSAAN", "SJK"), ("SEKOLAH MENENGAH KEBANGSAAN", "SMK"),
                  ("SEKOLAH KEBANGSAAN", "SK"), ("SEKOLAH MENENGAH", "SM"), ("SEKOLAH RENDAH", "SR"), ("SEKOLAH", "Sekolah")]
_KEEP_UPPER = {"FELDA", "FELCRA", "RISDA", "LKTP", "LDG", "RPS", "SJK", "SMK", "SK", "II", "III", "IV"}


def school_short(name) -> str:
    """MOE school name in its usual short form: 'SEKOLAH KEBANGSAAN NANGA LIPUS' -> 'SK Nanga Lipus'.
    Only reformats the MOE name (prefix abbreviated, rest in title case); never invents one."""
    if not isinstance(name, str) or not name.strip():
        return DASH
    n = " ".join(name.split()).upper()
    pre = ""
    for long, short in _SCHOOL_PREFIX:
        if n.startswith(long + " ") or n == long:
            pre, n = short, n[len(long):].strip()
            break

    def word(w):
        core = w.strip("().,&")
        if core in _KEEP_UPPER or (core and not any(v in core for v in "AEIOU") and not core.isdigit() and len(core) > 3):
            return w
        return w.capitalize() if not w.startswith("(") else "(" + w[1:].capitalize()

    rest = " ".join(word(w) for w in n.split())
    return f"{pre} {rest}".strip()
# Label for every total of the tower-vs-satellite cost screen (e.g. the national RM0.44bn): never a total across types
REF_COST = "reference: cost if every settlement without a nearby network were served by towers or satellite only"

def ramp_bin(share, ramp=TAKEUP_RAMP):
    """Index of share (0-1) in len(ramp) equal bins (the top bin includes 1), or None if missing."""
    if not isnum(share):
        return None
    return min(int(float(share) * len(ramp)), len(ramp) - 1)

# --- plain names on screen (technical names go in tooltips and on the Method page) ---
NEED = "Need score"                      # the Connectivity Gap Index (CGI)
NEED_TECH = "Need score (Connectivity Gap Index, 0 = best, 1 = worst nationally)"
REACH = "People reached per RM1m"        # estimated beneficiaries per RM1m

# --- confidence labels: word + colour, beside every estimate. Rule (also on the Method page):
#   Solid          official figures used as published (DOSM state and district tables, Hansard, the cited
#                  coverage figure, MOE school list)
#   Indicative     our estimates and proxies built from public data (Ookla-based proxies, settlement types,
#                  people offline, costs, Need score and its ranks, which come with ranges)
#   Low confidence a small inferred DOSM sample (small_sample_flag) or a screen that validates poorly against an
#                  official count (schools screen vs Hansard)
CONF = {"solid": ("Solid", "#1f6f4b", "#e3f1e9"), "indicative": ("Indicative", "#7a5200", "#fbf0d6"),
        "low": ("Low confidence", "#a1302a", "#f9e3e1")}
CONF_RULE = [
    ("solid", "Official figures used as published: DOSM survey tables (state level, and districts with an adequate "
              "sample), Hansard, the cited network-coverage figure, the MOE school list."),
    ("indicative", "Our estimates and proxies built from public data: anything from Ookla tests (signal, take-up "
                   "proxy), settlement types, people offline, costs, the Need score and its ranks (shown with ranges)."),
    ("low", "Rests on a small DOSM sample (flagged from our inferred sample size; its margin of error is shown), or a "
            "screen that matches an official count poorly (the schools screen vs Hansard)."),
]


def conf_badge(level: str | None) -> str:
    """Confidence label as HTML: a coloured dot and the word (never colour alone)."""
    if level not in CONF:
        return ""
    word, fg, bg = CONF[level]
    return (f"<span title='Confidence: see Method & limitations' style='background:{bg};color:{fg};border-radius:10px;"
            f"padding:1px 8px;font-size:0.78rem;font-weight:600;white-space:nowrap;display:inline-block;"
            f"line-height:1.6'>● {word}</span>")


def finding(title: str, subtitle: str | None = None, conf: str | None = None, level: int = 3) -> None:
    """Section title written as a finding (numbers read from data), with the descriptive title kept as a subtitle."""
    st.markdown(f"{'#' * level} {title}")
    bits = [f"<span>{subtitle}</span>"] if subtitle else []
    if conf:
        bits.append(conf_badge(conf))
    if bits:
        st.markdown(f"<div style='color:{INK_2};font-size:0.9rem;margin:-0.7rem 0 0.6rem 0;display:flex;gap:10px;"
                    f"flex-wrap:wrap;align-items:center'>{''.join(bits)}</div>", unsafe_allow_html=True)


def est_pct(v, moe=None, d: int = 0) -> str:
    """'estimated 62% (±13 points)' where a margin exists, else '62.0%'."""
    if not isnum(v):
        return DASH
    return f"estimated {v:.{d}f}% (±{moe:.0f} points)" if isnum(moe) else f"{v:.1f}%"


def about_one_in(share) -> str:
    """0.19 -> 'about 1 in 5'; shares above one half use 'about N in 10'."""
    if not isnum(share) or share <= 0:
        return DASH
    return f"about 1 in {round(1 / share)}" if share <= 0.5 else f"about {round(10 * share)} in 10"


# --- shared wording (reviewed) ---
BENEFIT = "estimated beneficiaries per RM1m"
BENEFIT_RANK = "estimated-beneficiaries-per-RM1m rank"
INFERRED_N = "inferred sample size"
MOE_TXT = "approximate margin of error (simple random-sampling formula)"
NOT_DOSM = "These are our estimates from DOSM's published percentages, not figures DOSM publishes."
TAKEUP_TXT = ("Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may "
              "matter as much as new infrastructure.")
COST_SCREEN = ("Cost screen, not a full cost-benefit comparison: households are assumed equal across a district's "
               "rural schools, and towers and satellite are different services (a tower also serves mobile users and "
               "roads; satellite serves single homes).")


def caveat(text: str = COST_SCREEN) -> None:
    st.markdown(f"<div style='border-left:3px solid {MUTED_LIGHT};padding:2px 10px;color:{INK_2};font-size:0.85rem'>"
                f"{text}</div>", unsafe_allow_html=True)

OSM_CREDIT = "© OpenStreetMap contributors"
BASEMAP_CREDIT = "Basemap © OpenStreetMap contributors © CARTO"


def hex_rgb(h: str, alpha: int = 255) -> list[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def page(title: str, intro: str | None = None) -> None:
    st.title(title)
    if intro:
        st.markdown(f"<p style='color:{INK_2};margin-top:-0.6rem'>{intro}</p>", unsafe_allow_html=True)


_SENTENCE_END = __import__("re").compile(r"(?<!e\.g\.)(?<!i\.e\.)(?<!vs\.)(?<=[a-z0-9%)\]][.])\s+(?=[A-Z(])")


def _split_first(text: str) -> tuple[str, str]:
    """First sentence and the rest ('W.P. Kuala Lumpur', 'e.g.' and decimals are not sentence ends)."""
    parts = _SENTENCE_END.split(text.strip(), maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def what(text: str | list[str], data: str | None = None, conf: str | None = None) -> None:
    """'What this shows' caption under a chart or table, with the data source and year.
    One clear sentence stays visible (the first point of a list, or the first sentence of a text); the rest goes
    into a small 'More detail' fold, so nothing (caveat or source) is removed. The data badge is always visible."""
    # the data badge sits on its own line; "What this shows:" starts on the next one
    chip = (f"<span style='background:#f3f2ee;border-radius:4px;padding:1px 6px;color:{INK_2};"
            f"display:inline-block;line-height:1.6;margin-bottom:3px'>Data: {data}</span>") if data else ""
    chip = (chip + (" " + conf_badge(conf) if conf else "") + "<br/>") if (chip or conf) else ""
    if isinstance(text, (list, tuple)):
        first, rest = (text[0] if text else ""), list(text[1:])
    else:
        first, more = _split_first(text)
        rest = [more] if more else []
    more_html = ""
    if rest:
        if len(rest) > 1:
            body = ("<ul style='margin:0.2rem 0 0 0;padding-left:1.2rem'>"
                    + "".join(f"<li style='margin:0 0 2px 0'>{t}</li>" for t in rest) + "</ul>")
        else:
            body = f"<div style='margin:0.2rem 0 0 0'>{rest[0]}</div>"
        more_html = (f"<details style='margin:0.15rem 0 0 0'><summary style='cursor:pointer;color:{MUTED};"
                     f"font-size:0.82rem'>More detail</summary>{body}</details>")
    st.markdown(f"<div style='color:{INK_2};font-size:0.88rem;margin:-0.4rem 0 0.8rem 0'>{chip}"
                f"<b>What this shows:</b> {first}{more_html}</div>", unsafe_allow_html=True)


def next_step(page: str, label: str, why: str) -> None:
    """'Next' card at the end of a page that walks the user journey:
    Overview → Sarawak map → District profile → Schools → Where to invest → Method."""
    st.markdown(f"<div style='margin-top:1.6rem;color:{INK_2};font-size:0.9rem'><b>Next:</b> {why}</div>",
                unsafe_allow_html=True)
    st.page_link(page, label=label, icon=":material/arrow_forward:")


def go_to_district(state: str, district: str) -> None:
    """Open District profile with this district preselected."""
    st.session_state["detail_state"] = state
    st.session_state["detail_district"] = district
    st.switch_page("views/4_District_detail.py")


def footer(sources: list[str], osm: bool = False, basemap: bool = False) -> None:
    from app_utils import data  # lazy: data does not import ui, but keep ui importable on its own

    st.divider()
    lines = [f"- {s}" for s in sources]
    if osm:
        lines.append(f"- District boundaries in Sarawak: {OSM_CREDIT} (ODbL); elsewhere DOSM (2022)")
    if basemap:
        lines.append(f"- {BASEMAP_CREDIT}")
    st.markdown(f"<div style='color:{MUTED};font-size:0.8rem'><b>Sources</b></div>", unsafe_allow_html=True)
    st.markdown("\n".join(lines), help=None)
    app = data.yaml_config("app")
    st.markdown(f"<div style='color:{MUTED};font-size:0.8rem;margin-top:0.4rem'>Last updated {app['last_updated']} · "
                f"{app['team']} · {app['event']} · Data years: {data.data_years()}</div>", unsafe_allow_html=True)


def style(fig: go.Figure, height: int = 420, legend: bool = True, **layout) -> go.Figure:
    base = dict(
        height=height, template="none", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK_2, size=13),
        margin=dict(l=10, r=20, t=30, b=10), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=MUTED_LIGHT),
    )
    base.update(layout)  # caller overrides win
    fig.update_layout(**base)
    axis = dict(gridcolor=GRID, linecolor=MUTED_LIGHT, zerolinecolor=MUTED_LIGHT, tickfont=dict(color=MUTED),
                title_font=dict(color=INK_2))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


# --- safe formatting helpers (NaN / None -> "–") ---
DASH = "–"


def isnum(v) -> bool:
    """True for a real, finite number (not None / NaN / pd.NA)."""
    try:
        return v is not None and v == v and float(v) not in (float("inf"), float("-inf"))
    except (TypeError, ValueError):
        return False


def fmt_num(v, fmt: str = ",.0f", prefix: str = "", suffix: str = "") -> str:
    return f"{prefix}{v:{fmt}}{suffix}" if isnum(v) else DASH


def fmt_int(v) -> str:
    return f"{int(v):,}" if isnum(v) else DASH


def fmt_pct(v, d: int = 1) -> str:
    return f"{v:.{d}f}%" if isnum(v) else DASH


def fmt_rm(v) -> str:
    """RM amounts: RMx.xxbn at or above RM1bn, RMx.xm at or above RM1m, otherwise RMxk (so small
    amounts never show as RM0.0m)."""
    if not isnum(v):
        return DASH
    if abs(v) >= 1e9:
        return f"RM{v / 1e9:,.2f}bn"
    if abs(v) >= 1e6:
        return f"RM{v / 1e6:,.1f}m"
    return f"RM{v / 1e3:,.0f}k" if v else "RM0"


def range_text(lo, hi) -> str:
    return f"{int(round(lo))}–{int(round(hi))}" if isnum(lo) and isnum(hi) else DASH


def rank_range(rank, lo, hi) -> str:
    """'12 (range 9–14)'; just the rank if the range is missing; '–' if no rank."""
    if not isnum(rank):
        return DASH
    return f"{int(rank)} (range {range_text(lo, hi)})" if isnum(lo) and isnum(hi) else f"{int(rank)}"


def rank_short(rank, lo, hi) -> str:
    """'12 (9–14)' for tables; just the rank if the range is missing; '' if no rank."""
    if not isnum(rank):
        return ""
    return f"{int(rank)} ({range_text(lo, hi)})" if isnum(lo) and isnum(hi) else f"{int(rank)}"


def safe_div(num, den):
    return num / den if isnum(num) and isnum(den) and den != 0 else float("nan")


def moe_text(moe) -> str:
    """Caption for an access figure; empty when there is no inferred margin."""
    return (f"±{moe:.0f} points: approximate margin of error (simple random-sampling formula; our estimate)"
            if isnum(moe) else "")


def moe_badge(col, moe) -> None:
    """Margin-of-error caption under a metric, only when one exists."""
    t = moe_text(moe)
    if t:
        col.caption(t)


def small_sample_banner(name: str, n, moe) -> None:
    """Low-confidence warning for small-sample districts (degrades gracefully if n or MOE is missing)."""
    parts = []
    if isnum(n):
        parts.append(f"{INFERRED_N} about {int(n)} households")
    if isnum(moe):
        parts.append(f"{MOE_TXT} ±{moe:.0f} points")
    detail = (": " + ", ".join(parts) + ".") if parts else "."
    st.warning(f"**Low confidence.** {name}'s DOSM figure appears to rest on a small sample{detail} "
               f"{NOT_DOSM} Treat its ranks as ranges, not exact positions.", icon="⚠️")


# --- display tables: formatted strings, "—" for missing values, numbers right-aligned ---
TABLE_DASH = "—"


def cell(v, fmt=None) -> str:
    """One table cell as text. fmt: a format spec (',.1f'), a callable, or None for text. Missing -> '—'."""
    if callable(fmt):
        out = fmt(v)
        return out if isinstance(out, str) and out not in ("", DASH) else TABLE_DASH
    if fmt is None:
        return v if isinstance(v, str) and v.strip() else TABLE_DASH
    return format(v, fmt) if isnum(v) else TABLE_DASH


def table(df, spec: list, *, height: int | str = "auto", download: str | None = None,
          notes: list[str] | None = None) -> None:
    """Show df as a clean display table. spec: [(source column, short label, fmt[, help])], fmt as in cell();
    keep labels short so the table fits at 1366 px and put the full description in help (shown on hover).
    Columns with a fmt are right-aligned; the first column is pinned for horizontal scroll on phones.
    download: a file name to add a 'Download this table (CSV)' button with the same rows and columns
    (numbers as numbers, at the displayed precision) and the notes as '#' lines at the top."""
    import pandas as pd

    spec = [tuple(x) + (None,) * (4 - len(x)) for x in spec]
    out = pd.DataFrame({label: [cell(v, fmt) for v in df[src]] for src, label, fmt, _ in spec})
    cfg = {label: st.column_config.TextColumn(label, help=hlp, alignment="right" if fmt is not None else "left",
                                              pinned=(i == 0))
           for i, (src, label, fmt, hlp) in enumerate(spec)}
    st.dataframe(out, hide_index=True, width="stretch", height=height, column_config=cfg)
    if download:
        raw = pd.DataFrame({label: _export_col(df[src], fmt) for src, label, fmt, _ in spec})
        download_csv(raw, download, "Download this table (CSV)", notes or [])


def _export_col(col, fmt):
    """A table column for CSV: numbers rounded to the displayed decimals, text as shown, missing left empty."""
    import re

    import pandas as pd

    if isinstance(fmt, str) and fmt.endswith("f"):
        m = re.search(r"\.(\d+)f$", fmt)
        nd = int(m.group(1)) if m else 0
        vals = [round(float(v), nd) if isnum(v) else None for v in col]
        return pd.array([None if v is None else int(v) for v in vals], dtype="Int64") if nd == 0 else vals
    return [None if (c := cell(v, fmt)) == TABLE_DASH else c for v in col]


def slug(name: str) -> str:
    """File-name part from a district or scope name: 'Kota Kinabalu' -> 'kota_kinabalu'."""
    import re

    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def download_csv(df, filename: str, label: str, notes: list[str], key: str | None = None) -> None:
    """st.download_button for df as CSV, with notes (sources, 'estimates') as '#' lines at the top.
    UTF-8 with BOM so Excel shows en dashes and accents correctly."""
    head = "".join(f"# {n}\n" for n in notes)
    st.download_button(label, (head + df.to_csv(index=False)).encode("utf-8-sig"), file_name=filename,
                       mime="text/csv", icon=":material/download:", key=key or f"dl_{filename}")


def fallback(text: str) -> None:
    """Short message shown instead of a chart or figure that cannot be computed."""
    st.info(text, icon="ℹ️")


# --- district action plan ---
TOWER_WIDER = "Towers bring wider benefits (mobile coverage on roads and farms) that this cost screen does not value."
GROUND_CHECKS = [
    "**Power:** reliable electricity for the terminal, day and night.",
    "**Sky view:** a clear view of the sky; tall forest and hills can block the signal.",
    "**Monthly fee:** who pays it, and for how long.",
    "**Repairs:** who fixes or replaces the kit, and how quickly.",
]


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _rank_line(label: str, rank, of, lo, hi) -> str:
    if not isnum(rank):
        return ""
    rng = f" (range {range_text(lo, hi)})" if isnum(lo) and isnum(hi) else ""
    of_txt = f" of {int(of)}" if isnum(of) else ""
    return f"{label} need rank **{int(rank)}**{of_txt}{rng}."


def _stat(value: str, label: str) -> str:
    """Big number with a small label under it (HTML, for type cards)."""
    return (f"<div><div style='font-size:1.55rem;font-weight:650;color:{INK};line-height:1.15'>{value}</div>"
            f"<div style='font-size:0.75rem;color:{MUTED}'>{label}</div></div>")


def type_card(code: str, label: str, stats_html: str, tech: str, cost: str) -> str:
    """One settlement-type card: the map's type colour as top stripe and dot (identity); numbers stay in ink."""
    col = TYPE_COLOURS.get(code, MUTED_LIGHT)
    return (f"<div style='border:1px solid {GRID};border-top:5px solid {col};border-radius:8px;padding:10px 12px;"
            f"background:#ffffff'>"
            f"<div style='font-weight:600;color:{INK};font-size:0.92rem'><span style='color:{col}'>●</span> "
            f"{code}. {label}</div>"
            f"<div style='display:flex;gap:18px;flex-wrap:wrap;margin:6px 0 8px 0'>{stats_html}</div>"
            f"<div style='font-size:0.8rem;color:{INK_2};line-height:1.35'><b>Candidate technologies (screening):</b> "
            f"{tech}</div>"
            f"<div style='font-size:0.8rem;color:{INK_2};line-height:1.35;margin-top:5px'><b>Five-year cost:</b> "
            f"{cost}</div></div>")


def card_grid(cards: list[str], min_px: int = 220) -> None:
    """Cards side by side; they wrap to one per row on a phone."""
    st.markdown(f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax({min_px}px,1fr));gap:10px;"
                f"margin:0.2rem 0 0.8rem 0'>{''.join(cards)}</div>", unsafe_allow_html=True)


def metric_cards(items: list[tuple], min_px: int = 200) -> None:
    """Headline numbers as clean cards whose labels wrap (st.metric truncates long labels).
    items: (label, value, help or None); help shows on hover over the card."""
    import html
    cards = [f"<div title='{html.escape(h or '', quote=True)}' style='border:1px solid {GRID};border-radius:8px;"
             f"padding:12px 14px;background:#ffffff'><div style='font-size:0.85rem;color:{INK_2};line-height:1.3'>"
             f"{lab}</div><div style='font-size:2rem;font-weight:600;color:{INK};line-height:1.25;margin-top:4px'>"
             f"{val}</div></div>" for lab, val, h in items]
    card_grid(cards, min_px)


def action_plan(r, fixes: dict, *, n_national, n_state, host: str | None, sources: str,
                on_host_click=None, types=None) -> None:
    """Summary card for one district: 'If I'm responsible for this district, what should I do?'

    r        one row of data.district_table()
    fixes    {category: row with n, people, cost_main, cost_lite} from data.fix_breakdown(); {} if none
    n_*      number of ranked districts nationally / in the district's state (for 'rank X of N')
    host     district whose polygon contains this one (no-boundary districts), else None
    types    data.district_types(state, district): settlements, people, candidate technologies, cost per type
    Never raises on missing values: every figure degrades to a short message."""
    name, state = r.district, r.state
    with st.container(border=True):
        st.markdown(f"### What to do in {name}")
        st.markdown(f"<p style='color:{INK_2};margin-top:-0.6rem'>If you are responsible for this district: "
                    "how great the need is, what kinds of rural settlement it has, candidate technologies (screening) "
                    "and the estimated cost where one can be costed.</p>",
                    unsafe_allow_html=True)

        # 1. Need
        st.markdown(f"**1. Need score** {conf_badge('low' if bool(r.get('small_sample_flag')) is True else 'indicative')}",
                    unsafe_allow_html=True)
        if isnum(r.get("rank_national")):
            lines = [_rank_line("National", r.rank_national, n_national, r.get("rank_national_p05"), r.get("rank_national_p95"))]
            if state == "Sarawak" and isnum(r.get("rank_sarawak")):
                lines.append(_rank_line("Sarawak", r.rank_sarawak, n_state, r.get("rank_sarawak_p05"), r.get("rank_sarawak_p95")))
            st.markdown(" ".join(lines) + " Rank 1 = largest gap. Ranges are the 5th–95th percentile rank across "
                        "random weightings of the Need score (Connectivity Gap Index).")
        elif not r.get("has_boundary", True):
            st.markdown("Not ranked: there is no map boundary for this district, so it has no Ookla speeds or Need score"
                        + (f". Its area, tests and rural schools are counted under **{host}**." if host else "."))
        else:
            st.markdown("Not ranked: the Need score could not be computed for this district.")
        flagged = r.get("small_sample_flag")
        if isnum(flagged) and bool(flagged):
            small_sample_banner(name, r.get("implied_sample_n"), r.get("internet_moe95_pp"))
        # the Sarawak map focuses a district from ?district=...; only districts drawn on it get the link
        if state == "Sarawak" and r.get("has_boundary", False) and isnum(r.get("rank_sarawak")):
            st.page_link("views/3_Sarawak_map.py", label=f"Show {name} on the Sarawak map", icon=":material/map:",
                         query_params={"district": name})

        # 2. What to do
        st.markdown(f"**2. What to do (estimates)** {conf_badge('indicative')}", unsafe_allow_html=True)
        tk, sat, tw = (fixes.get(c) for c in ("takeup_gap", "satellite", "tower"))
        n = {c: int(f["n"]) if f is not None and isnum(f["n"]) else 0 for c, f in
             (("takeup_gap", tk), ("satellite", sat), ("tower", tw))}
        if not fixes:
            if not r.get("has_boundary", True):
                st.markdown("No settlement plan of its own" + (f": its rural schools are planned under {host}." if host else "."))
                if host and on_host_click and st.button(f"Open {host}", key=f"ap_host_{state}_{name}",
                                                        icon=":material/arrow_forward:"):
                    on_host_click(state, host)
            else:
                pw = r.get("people_without_home_internet")
                st.markdown(f"{name} has no rural MOE school, so no rural settlements are costed."
                            + (f" An estimated {pw:,.0f} people in the district live in homes without internet;"
                               " for them, take-up support (subsidies, awareness, help signing up) is the main lever."
                               if isnum(pw) and pw > 0 else ""))
        else:
            none_lack = "DOSM data suggest no households here lack home internet"  # access gap 0%
            from app_utils.explainers import gloss  # lazy: explainers imports ui
            cards = []
            for t in (types.itertuples() if types is not None else []):
                if t.settlement_type == "A":
                    cost = ("not costed: take-up support has no public cost source. <i>Proxy: an Ookla "
                            "fixed-broadband test within 2 km of the school, not a coverage map.</i>")
                elif isnum(t.cost):
                    cost = f"{fmt_rm(t.cost)} ({cost_basis_short(t.type_cost_basis)}, estimate)"
                    if round(t.cost) == 0:  # access gap 0%: nothing to pay for
                        cost = "none: no households here lack home internet"
                    elif t.settlement_type == "D" and round(t.people) == 0:
                        cost = f"{fmt_rm(t.cost)}: the school's satellite link only (estimate)"
                else:
                    cost = NOT_COSTED
                ppl = (_stat(fmt_num(t.people), "people offline (est.)") if round(t.people) > 0
                       else f"<div style='font-size:0.78rem;color:{INK_2};max-width:11rem'>{none_lack}</div>")
                cards.append(type_card(t.settlement_type, t.type_label,
                                       _stat(f"{int(t.n):,}", "settlement" + ("" if int(t.n) == 1 else "s")) + ppl,
                                       gloss(t.candidate_technologies), cost))
            if cards:
                card_grid(cards)
            items = []
            if not (n["satellite"] or n["tower"]):
                lever = ("so take-up support is the main lever." if tk is not None and round(tk["people"]) > 0
                         else "and no take-up gap is estimated either.")
                items.append("- **New infrastructure:** none costed. Every rural settlement has a fixed network likely "
                             f"nearby (our proxy), {lever}")
            else:
                lo, hi = sorted([sum(f["cost_lite"] for f in fixes.values()), sum(f["cost_main"] for f in fixes.values())])
                rng = fmt_rm(hi) if fmt_rm(lo) == fmt_rm(hi) else f"{fmt_rm(lo)}–{fmt_rm(hi)}, Lite to Residential plan"
                items.append(f"- **Reference cost** (tower or satellite only, used in the rankings): {rng}. Not a "
                             f"total of the cards above: types A and C are not costed. Details in the Reference cost "
                             f"tab below. {TOWER_WIDER}")
            st.markdown("\n".join(items))

        # 3. Check on the ground
        present = set(types.settlement_type) if types is not None and len(types) else set()
        checks = []
        if present & {"D", "C"} or n["satellite"]:
            checks += GROUND_CHECKS
        if present & {"E", "B"}:
            checks.append("**Mobile signal indoors:** coverage maps are mainly outdoor; test inside homes and check "
                          "the nearest site has spare capacity for home broadband (FWA).")
        if present & {"C", "B"}:
            checks.append("**Backhaul:** a line of sight for a microwave link, or a satellite link, to the nearest network.")
        if checks:
            st.markdown("**3. Check on the ground before choosing a technology**")
            st.markdown("\n".join(f"- {c}" for c in checks))

        caveat()
        st.caption(f"Data: {sources}. All costs and people counts are estimates.")
