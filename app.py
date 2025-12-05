import io
from datetime import datetime
import re

import numpy as np
import pandas as pd
import streamlit as st

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from utils import normalize_activities_df
from vendors import get_potential_vendors_for_topics
from scoring import apply_intent_scoring
from external_triggers import find_best_trigger_for_company
from filters import (
    LIFECYCLE_CATEGORIES,
    LIFECYCLE_TO_TOPICS,
    get_topics_for_lifecycle,
    apply_lifecycle_topic_filters,
)

# ------------------------
# LSC Buyer Journey Intelligence Engine
# ------------------------

# Internal canonical required fields (after normalization)
REQUIRED_COLUMNS = [
    "reader_company",
    "first_name",
    "last_name",
    "activity_date",
    "activity_source",
    "content_title",
    "content_bj_label",
    "specifics",
    "content_topics",
    "content_source",
]

STAGE_ORDER = ["Awareness", "Problem Definition", "Solution Exploration", "Vendor Evaluation"]

STAGE_COLOR = {
    "Vendor Evaluation": "FF0000",  # red
    "Solution Exploration": "FFA500",  # orange
    "Problem Definition": "FFFF00",  # yellow
    "Awareness": "C0C0C0",  # gray
}


### --- Helpers for v5-style logic ---


def extract_primary_topic(row):
    """Return a comma-separated primary topic string based on content_topics, content_title, specifics."""
    parts = []
    for c in ["content_topics", "content_title", "specifics"]:
        val = row.get(c) if isinstance(row, dict) else (row.get(c) if c in row else None)
        if pd.isna(val) or val is None or str(val).strip() == "":
            continue
        toks = re.split(r"[,;|/\n]", str(val))
        toks = [t.strip() for t in toks if t and len(t.strip()) > 1]
        parts.extend(toks)

    if not parts:
        return ""
    freq = {}
    for p in parts:
        freq[p] = freq.get(p, 0) + 1
    top = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:3]
    return ",".join([t[0] for t in top])


def deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate column names by keeping the first occurrence."""
    if df.empty:
        return df
    # Check for duplicates
    if len(df.columns) == len(set(df.columns)):
        return df  # No duplicates
    
    # Use iloc to select columns by position, avoiding issues with duplicate names
    seen = set()
    keep_indices = []
    for i, col in enumerate(df.columns):
        if col not in seen:
            keep_indices.append(i)
            seen.add(col)
    
    # Select only the unique columns by index
    result = df.iloc[:, keep_indices].copy()
    return result


def normalize_org_key(name: str) -> str:
    """Normalize organization name for grouping: lowercase, remove punctuation,
    strip common business suffixes, and collapse whitespace. Returns a short
    normalized key used only for grouping (not for display).
    """
    if name is None:
        return ""
    s = str(name)
    if s.strip() == "":
        return ""
    # lowercase
    t = s.lower()
    # remove punctuation
    t = re.sub(r"[^\w\s]", " ", t)
    # remove common business suffixes
    t = re.sub(r"\b(?:inc|incorporated|ltd|limited|llc|gmbh|sas|sa|corp|corporation|co|company|plc|bv|ag|pty|holding|holdings)\b", "", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


VENDOR_LOOKUP = {
    "manufacturing": ["Cytiva", "Sartorius", "Thermo Fisher Scientific", "Repligen", "Pall (Cytiva)", "MilliporeSigma"],
    "qa/qc": ["Waters", "Agilent", "Thermo Fisher Scientific", "Shimadzu", "SCIEX", "Bruker"],
    "upstream": ["Cytiva", "Sartorius", "Repligen", "Eppendorf", "PBS Biotech"],
    "downstream": ["Cytiva", "Sartorius", "Tosoh Bioscience", "Repligen"],
    "analytical": ["Waters", "Agilent", "Thermo Fisher Scientific", "SCIEX", "Shimadzu"],
    "all molecules": ["Cytiva", "Sartorius", "Thermo Fisher Scientific", "MilliporeSigma"],
}


def map_topics_to_vendors(primary_topic_str: str):
    if not primary_topic_str:
        return ["Cytiva", "Sartorius", "Thermo Fisher Scientific", "MilliporeSigma", "Repligen", "Pall (Cytiva)"]
    vendors = []
    toks = [t.strip().lower() for t in primary_topic_str.split(",") if t.strip()]
    for t in toks:
        for k, vs in VENDOR_LOOKUP.items():
            if k in t or t in k:
                vendors.extend(vs)
    if not vendors:
        return ["Cytiva", "Sartorius", "Thermo Fisher Scientific", "MilliporeSigma", "Repligen"]
    seen = set()
    out = []
    for v in vendors:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def extract_vendors_evaluated(row):
    text = " ".join([str(row.get(c, "")) for c in ["content_source", "specifics", "client", "newsletter_name"] if not pd.isna(row.get(c, ""))])
    if not text:
        return ""
    found = set()
    possible = [
        "Cytiva", "Sartorius", "Thermo Fisher", "Thermo Fisher Scientific", "MilliporeSigma", "Pall", "Waters", "Agilent",
        "SCIEX", "Eppendorf", "Fujifilm Irvine Scientific", "Repligen", "Lonza", "Catalent", "Bio-Rad", "PBS Biotech",
        "Tosoh", "Shimadzu",
    ]
    for p in possible:
        if re.search(re.escape(p), text, flags=re.IGNORECASE):
            found.add(p)
    return ", ".join(sorted(found))


def detect_behavioral_triggers_and_flags(group_df: pd.DataFrame):
    rows_text = " ".join([str(x) for x in group_df.get("content_title", []) if not pd.isna(x)]) + " " + " ".join([str(x) for x in group_df.get("specifics", []) if not pd.isna(x)])
    flags = []
    triggers = set()
    explanation_parts = []

    # Determine non-newsletter rows based ONLY on the `activity_source` text.
    # Requirement: any flags or explanation text derived from activity/source
    # should appear only when the activity source itself is a non-empty, non-newsletter value.
    # Treat empty or missing activity_source as unknown and DO NOT count it as non-newsletter.
    asrc = group_df.get("activity_source", pd.Series([""] * len(group_df))).astype(object).fillna("").astype(str).str.lower().str.strip()
    # strict match for the word 'newsletter' to avoid partial matches
    is_news = asrc.str.contains(r"\bnewsletter\b", na=False)
    # Only treat rows as non-newsletter WHEN the activity_source explicitly contains
    # an explicit non-NL marker. This follows the user's instruction that generic
    # sources like 'webinar', 'event', or 'engagement' should NOT be considered Non-NL.
    non_nl_marker = asrc.str.contains(r"\b(?:non[\s_-]?nl|non[\s-]?newsletter|nonnewsletter)\b", na=False)
    non_nl = group_df[non_nl_marker]

    # tuned heuristic (conservative): mark Non-NL only when it's a strong signal.
    total_rows = len(group_df)
    non_nl_count = len(non_nl)
    pct_non_nl = (non_nl_count / total_rows) if total_rows > 0 else 0.0

    # compute process and late-stage signals on the full set of activity text (all rows).
    # Rationale: webinars/events and other generic activity_source values should still
    # surface process/late-stage interest signals even when they are NOT explicitly
    # labeled as Non-NL. However, the explicit "Non-NL engagement" wording should
    # only be added when explicit non-nl markers exist in `activity_source`.
    combined_all_text = " ".join([str(x) for x in group_df.get("content_title", []) if not pd.isna(x)]) + " " + " ".join([str(x) for x in group_df.get("specifics", []) if not pd.isna(x)])
    proc_hits = len(re.findall(r"(?:upstream|downstream|process|scale-up|tech transfer|manufactur|chromatograph|viral clearance|polish|isolation|purification)", combined_all_text, flags=re.IGNORECASE))
    late_hits = 1 if re.search(r"(?:compare|comparison|vs\b|pricing|quote|rfp|vendor evaluation|vendor eval|vendor|evaluation|spec sheet|datasheet|benchmark|compare to|comparison study)", combined_all_text, flags=re.IGNORECASE) else 0

    # If any explicit non-newsletter marker appears in `activity_source`, mark Non-NL.
    # This follows the user's requirement: only report Non-NL when the uploaded
    # file explicitly contains non-newsletter markers in the activity source.
    bj_vals = [str(x).lower() for x in group_df.get("content_bj_label", []) if not pd.isna(x)]
    combined_text = " ".join([str(x) for x in group_df.get("content_title", []) if not pd.isna(x)]) + " " + " ".join([str(x) for x in group_df.get("specifics", []) if not pd.isna(x)])
    inferred_stage = None
    if any("vendor" in v or "evaluation" in v or "eval" in v for v in bj_vals):
        inferred_stage = "Vendor Evaluation"
    elif re.search(r"(compare|comparison|vs\b|pricing|quote|rfp|vendor|evaluation)", combined_text, flags=re.IGNORECASE):
        inferred_stage = "Vendor Evaluation"
    elif re.search(r"(solution|product|datasheet|whitepaper|case study|webinar|feature|use case|workflow)", combined_text, flags=re.IGNORECASE):
        inferred_stage = "Solution Exploration"
    elif re.search(r"(problem|pain|challenge|need|gap|issue|requirement|diagnos)", combined_text, flags=re.IGNORECASE):
        inferred_stage = "Problem Definition"
    else:
        inferred_stage = "Awareness"

    # tuned thresholds
    # Strict behavior: if any row's `activity_source` explicitly matches the
    # non-newsletter pattern, add the Non-NL flag and explanation. Do not infer
    # Non-NL indirectly from other activity types.
    if non_nl_count >= 1:
        flags.append("\U0001F525 Non-NL engagement")
        explanation_parts.append("Direct (Non-NL) visit rather than newsletter click")

    late_stage_keywords = r"(?:compare|comparison|vs\b|pricing|quote|rfp|vendor evaluation|vendor eval|vendor|evaluation|spec sheet|datasheet|benchmark|compare to|comparison study)"
    # evaluate late-stage and process keywords on the full activity text so that
    # webinars/events and other generic activity sources can still trigger process
    # and late-stage flags. Note: the explicit Non-NL wording is still gated by
    # the non_nl markers above (cond_high/cond_stage) and will not be set unless
    # explicit non-newsletter rows exist.
    search_text_for_stage = combined_all_text
    if re.search(late_stage_keywords, search_text_for_stage, flags=re.IGNORECASE):
        flags.append("\U0001F4C4 Late-stage content")
        triggers.add("Vendor/option comparison")
        explanation_parts.append("Engaging with late-stage comparison/evaluation content")

    process_keywords = r"(?:upstream|downstream|process|scale-up|tech transfer|manufactur|chromatograph|viral clearance|polish|isolation|purification)"
    if len(re.findall(process_keywords, search_text_for_stage, flags=re.IGNORECASE)) >= 2:
        flags.append("\U0001F504 Deep process interest")
        triggers.add("GMP / clinical manufacturing")
        explanation_parts.append("Exploring process/solution workflows")

    problem_keywords = r"(?:problem|pain|challenge|issue|need|gap|failure|root cause)"
    # only consider problem/pain keywords in non-newsletter activity text
    if search_text_for_stage and re.search(problem_keywords, search_text_for_stage, flags=re.IGNORECASE):
        explanation_parts.append("Looking at challenge/problem-focused content")

    expl = []
    for part in explanation_parts:
        if part not in expl:
            expl.append(part)

    return {
        "flags": ", ".join(flags),
        "behavioral_triggers": ", ".join(sorted(triggers)),
        "explanation_parts": expl,
    }


def enrich_external_trigger_for_company(company_name: str):
    if not company_name or pd.isna(company_name):
        return ""
    cn = str(company_name).lower()
    if "samsung" in cn:
        return "Announced a large-scale CDMO expansion program in APAC."
    if "biocon" in cn:
        return "Inaugurated its first U.S. manufacturing facility, expanding global biologics production footprint."
    if "biontech" in cn:
        return "Investing in mRNA manufacturing capacity, including new mRNA facility initiatives."
    return ""


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize incoming LSC exports to a fixed internal schema.

    - Accepts multiple header variants and coalesces into canonical internal names
    - Errors only if required internal fields (REQUIRED_COLUMNS) are missing after normalization
    - Preserves extra columns
    - Creates optional columns when absent
    - Converts `activity_date` to datetime and strips whitespace
    """

    canonical_map = {
        # Reader Company
        "reader_company": "reader_company",
        "reader company": "reader_company",
        "reader_org": "reader_company",
        "reader org": "reader_company",
        "company": "reader_company",
        "company_name": "reader_company",

        # Names
        "first_name": "first_name",
        "firstname": "first_name",
        "last_name": "last_name",
        "lastname": "last_name",

        # Title
        "title": "title",

        # Dates
        "activity_date": "activity_date",
        "activity date": "activity_date",
        "activity_month": "activity_date",
        "engagement_date": "activity_date",

        # Activity / Source
        "activity_source": "activity_source",
        "activity source": "activity_source",
        "activity_type": "activity_source",
        "engagement_type": "activity_source",

        # Content
        "content_title": "content_title",
        "content title": "content_title",
        "raw_content_title": "content_title",
        "content_type": "content_type",
        "content type": "content_type",
        "content_buyer's_journey": "content_bj_label",
        "content buyer's journey": "content_bj_label",
        "content_bj_label": "content_bj_label",
        "content_topics": "content_topics",
        "content topics": "content_topics",
        "topics": "content_topics",
        "content_source": "content_source",
        "content source": "content_source",
        "specifics": "specifics",

        # Optional fields
        "email": "email",
        "newsletter_name": "newsletter_name",
        "newsletter name": "newsletter_name",
        "client": "client",
        "quality": "quality",
        "country": "country",
        "region": "region",
    }

    # group detected source columns to their canonical target
    norm_to_sources = {}
    for orig_col in list(df.columns):
        norm = orig_col.strip().lower().replace(" ", "_")
        target = canonical_map.get(norm)
        if target:
            norm_to_sources.setdefault(target, []).append(orig_col)

    # coalesce or rename
    for target, sources in norm_to_sources.items():
        if len(sources) == 1:
            df = df.rename(columns={sources[0]: target})
        else:
            # Prefer explicit "Activity Source" column over "Activity Type" when both exist.
            # Sort sources so that any source whose normalized name equals the target
            # appears first. This avoids taking an earlier column like 'Activity Type'
            # when a more specific 'Activity Source' column (e.g. 'Non-NL') is present.
            def _norm_name(s):
                return s.strip().lower().replace(" ", "_")

            sorted_sources = sorted(sources, key=lambda s: 0 if _norm_name(s) == target else 1)
            df[target] = df[sorted_sources].bfill(axis=1).iloc[:, 0]

    # verify required internal fields
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        examples = [
            "Reader Company", "First Name", "Last Name", "Title", "Activity Date",
            "Activity Source", "Content Title", "Content Buyer's Journey", "Specifics",
            "Content Topics", "Content Source",
        ]
        raise ValueError(f"Uploaded file is missing required fields after normalization: {missing}. Examples: {examples}")

    # optional fallbacks
    optional_cols = ["email", "newsletter_name", "quality", "product", "client", "country", "region"]
    for c in optional_cols:
        if c not in df.columns:
            df[c] = np.nan

    # convert dates
    if "activity_date" in df.columns:
        df["activity_date"] = pd.to_datetime(df["activity_date"], errors="coerce")

    # strip whitespace
    obj_cols = df.select_dtypes(include=[object]).columns.tolist()
    for c in obj_cols:
        df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)

    return df


def find_required_columns(df):
    df = normalize_columns(df)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return missing, df


def parse_dates(df, col="engagement_date"):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def stage_from_text(text: str):
    if pd.isna(text):
        return None
    t = str(text).lower()
    # heuristics
    if re.search(r"(demo|trial|pricing|rfp|quote|proposal|purchase|evaluation|vendor|vendor eval)", t):
        return "Vendor Evaluation"
    if re.search(r"(solution|product|datasheet|whitepaper|case study|webinar|feature|use case)", t):
        return "Solution Exploration"
    if re.search(r"(problem|pain|challenge|need|gap|issue|requirement|define|diagnos)", t):
        return "Problem Definition"
    if re.search(r"(newsletter|social|blog|press|awareness|announcement|advertis|marketing)", t):
        return "Awareness"
    # default fallback: Awareness
    return "Awareness"


@st.cache_data
def process_dataframe(df: pd.DataFrame, min_engagements: int = 5, rollup_base: bool = True):
    """Process normalized DataFrame into v5-style Individuals, Company_Combined and Sales_Hot_List.

    This function recreates the transformation, explanation, primary topic extraction,
    vendor mapping, vendor-evaluated extraction, behavioral triggers, and company-level
    summaries similar to the provided v5 reference.
    """

    # ensure expected internals exist
    for c in ["email", "first_name", "last_name", "reader_company", "activity_source", "product"]:
        if c not in df.columns:
            df[c] = np.nan

    # canonical person key: prefer email, else first+last+company
    df["email_norm"] = df["email"].astype(str).str.lower().str.strip()

    def person_key(row):
        em = str(row.get("email_norm", "")).strip()
        if em and em.lower() not in ["nan", "none", ""]:
            return em
        return (str(row.get("first_name", "")).strip() + "|" + str(row.get("last_name", "")).strip() + "|" + str(row.get("reader_company", "")).strip()).lower()

    df["person_key"] = df.apply(person_key, axis=1)

    # compute per-person aggregates
    grouped = df.groupby("person_key")

    records = []
    for key, g in grouped:
        g = g.sort_values(by=["activity_date"]) if "activity_date" in g.columns else g
        first = g.iloc[0]
        total_eng = int(g["activity_date"].count()) if "activity_date" in g.columns else g.shape[0]
        # last activity date
        last_dt = None
        if "activity_date" in g.columns:
            try:
                last_dt = pd.to_datetime(g["activity_date"], errors="coerce").max()
            except Exception:
                last_dt = None

        # Non-newsletter engagement count (conservative): count activity_source rows
        # that are non-empty and do NOT explicitly contain the word 'newsletter'
        try:
            asrc = g.get("activity_source", pd.Series([""] * len(g))).astype(object).fillna("").astype(str)
            non_nl_mask = ~asrc.str.contains(r"\bnewsletter\b", na=False, case=False) & asrc.str.strip().ne("")
            non_nl_count = int(non_nl_mask.sum())
        except Exception:
            non_nl_count = 0
        # Primary topic from group
        primary_topic = extract_primary_topic(g.iloc[0] if not g.empty else {})
        if not primary_topic:
            # try aggregate across rows
            primary_topic = extract_primary_topic({"content_topics": ", ".join([str(x) for x in g.get("content_topics", []) if not pd.isna(x)]),
                                                   "content_title": ", ".join([str(x) for x in g.get("content_title", []) if not pd.isna(x)]),
                                                   "specifics": ", ".join([str(x) for x in g.get("specifics", []) if not pd.isna(x)])})

        potential_vendors = map_topics_to_vendors(primary_topic)
        vendors_eval = extract_vendors_evaluated({
            "content_source": ", ".join([str(x) for x in g.get("content_source", []) if not pd.isna(x)]),
            "specifics": ", ".join([str(x) for x in g.get("specifics", []) if not pd.isna(x)]),
            "client": ", ".join([str(x) for x in g.get("client", []) if not pd.isna(x)]),
            "newsletter_name": ", ".join([str(x) for x in g.get("newsletter_name", []) if not pd.isna(x)]),
        })

        bt = detect_behavioral_triggers_and_flags(g)

        # determine buyer journey label using multi-factor rules
        combined_text = " ".join([str(x) for x in g.get("content_title", []) if not pd.isna(x)]) + " " + " ".join([str(x) for x in g.get("specifics", []) if not pd.isna(x)])
        label = "Awareness"
        # prefer explicit content_bj_label values if present in group
        bj_vals = [str(x).lower() for x in g.get("content_bj_label", []) if not pd.isna(x)]
        if any("vendor" in v or "evaluation" in v or "eval" in v for v in bj_vals):
            label = "Vendor Evaluation"
        elif re.search(r"(compare|comparison|vs\b|pricing|quote|rfp|vendor|evaluation)", combined_text, flags=re.IGNORECASE):
            label = "Vendor Evaluation"
        elif re.search(r"(solution|product|datasheet|whitepaper|case study|webinar|feature|use case|workflow)", combined_text, flags=re.IGNORECASE):
            label = "Solution Exploration"
        elif re.search(r"(problem|pain|challenge|need|gap|issue|requirement|diagnos)", combined_text, flags=re.IGNORECASE):
            label = "Problem Definition"
        else:
            label = "Awareness"

        # explanation assembly
        expl_parts = []
        if bt.get("explanation_parts"):
            expl_parts.extend(bt.get("explanation_parts"))
        if label == "Awareness" and not expl_parts:
            expl_parts.append("General interest in this topic area")

        explanation = " \u2022 ".join(expl_parts) if expl_parts else "General interest in this topic area"

        reason = ""
        if label == "Vendor Evaluation":
            reason = f"Actively comparing solutions in {primary_topic}; good timing for targeted outreach."
        else:
            reason = f"Early awareness in {primary_topic}; keep warm with high-level thought leadership."

        records.append({
            "Reader Company": first.get("reader_company", ""),
            "First Name": first.get("first_name", ""),
            "Last Name": first.get("last_name", ""),
            "Title": first.get("title", ""),
            "Total Engagements": total_eng,
            "Last_Activity_Date": last_dt,
            "Non_NL_Engagements": non_nl_count,
            "Buyer_Journey_Label": label,
            "Explanation": explanation,
            "Primary_Topic": primary_topic,
            "Potential_Vendors": ", ".join(potential_vendors),
            "Vendors_Evaluated": vendors_eval,
            "Buyer_Intensity_Flags": bt.get("flags", ""),
            "Behavioral_Trigger": bt.get("behavioral_triggers", ""),
            "External_Trigger (press release info, etc)": enrich_external_trigger_for_company(first.get("reader_company", "")),
            "Reason to Reach out": reason,
        })

    individuals_df = pd.DataFrame.from_records(records)
    # Remove duplicate columns if any
    individuals_df = deduplicate_columns(individuals_df)

    # ensure numeric
    if "Total Engagements" in individuals_df.columns:
        individuals_df["Total Engagements"] = individuals_df["Total Engagements"].astype(int)

    # Prepare for intent scoring: scoring expects `Total_Engagements`, `Last_Activity_Date`,
    # `Non_NL_Engagements`, `Buyer_Journey_Label`, `Vendors_Evaluated`, and `Reader Company`.
    indiv_for_scoring = individuals_df.copy()
    # create a scoring-friendly column name
    if "Total Engagements" in indiv_for_scoring.columns and "Total_Engagements" not in indiv_for_scoring.columns:
        indiv_for_scoring["Total_Engagements"] = indiv_for_scoring["Total Engagements"].astype(int)
    # Prefer `Reader Org` for grouping/scoring when available (fallback to `Reader Company`)
    if "Reader Org" in indiv_for_scoring.columns:
        # create a scoring-friendly `Reader Company` column that prefers Reader Org when present
        ro = indiv_for_scoring["Reader Org"].astype(str).fillna("").str.strip()
        rc = indiv_for_scoring.get("Reader Company", pd.Series([""] * len(indiv_for_scoring))).astype(str).fillna("").str.strip()
        indiv_for_scoring["Reader Company"] = ro.where(ro != "", rc)

    # company aggregation for team buying (now using the adjusted `Reader Company` column)
    comp_agg = indiv_for_scoring.groupby("Reader Company").agg(Company_Contact_Count=("Reader Company", "count")).reset_index()
    # attempt to compute intent scoring and derived buyer journey; fall back gracefully on error
    try:
        scored = apply_intent_scoring(indiv_for_scoring, comp_agg, org_column="Reader Org")
        # ensure we keep the original display naming
        if "Total_Engagements" in scored.columns and "Total Engagements" not in scored.columns:
            scored["Total Engagements"] = scored["Total_Engagements"].astype(int)
        individuals_df = scored
        # Remove duplicate columns from scored dataframe
        individuals_df = deduplicate_columns(individuals_df)
    except Exception:
        # scoring failed — ensure Derived_Buyer_Journey exists as a fallback copy
        if "Derived_Buyer_Journey" not in individuals_df.columns:
            individuals_df["Derived_Buyer_Journey"] = individuals_df.get("Buyer_Journey_Label", "")

    # filter by min engagements
    individuals_filtered = individuals_df[individuals_df["Total Engagements"] >= int(min_engagements)].copy()
    # Remove duplicate columns from individuals_filtered
    individuals_filtered = deduplicate_columns(individuals_filtered)
    # Company combined (group by normalized Reader Org)
    if individuals_filtered.empty:
        company_combined = pd.DataFrame(columns=["Reader Org", "Active_Individuals", "Dominant_Topic", "Team_Buying_Signal", "Behavioral_Triggers", "External_Trigger", "Product_Category"])
    else:
        inds_tmp = individuals_filtered.copy()
        # create a raw Reader Org field: prefer any existing 'Reader Org' else fall back to 'Reader Company'
        if "Reader Org" in inds_tmp.columns:
            inds_tmp["Reader_Org_Raw"] = inds_tmp["Reader Org"].astype(str).fillna("").str.strip()
        else:
            inds_tmp["Reader_Org_Raw"] = inds_tmp.get("Reader Company", "").astype(str).fillna("").str.strip()

        inds_tmp["Reader_Org_Norm"] = inds_tmp["Reader_Org_Raw"].apply(normalize_org_key)
        # optionally derive a base key (first token) to combine subsidiaries/variants
        if rollup_base:
            inds_tmp["Reader_Org_Base"] = inds_tmp["Reader_Org_Norm"].apply(lambda x: str(x).split()[0] if str(x).strip() else "")
            group_key = "Reader_Org_Base"
        else:
            group_key = "Reader_Org_Norm"

        comp_rows = []
        for base_key, cg in inds_tmp.groupby(group_key):
            # display name: most common original Reader Org text in this normalized group
            display_name = ""
            try:
                modes = cg["Reader_Org_Raw"].mode()
                if not modes.empty:
                    display_name = modes.iloc[0]
                else:
                    display_name = cg["Reader_Org_Raw"].dropna().astype(str).iloc[0] if not cg["Reader_Org_Raw"].dropna().empty else ""
            except Exception:
                display_name = cg["Reader_Org_Raw"].astype(str).iloc[0] if not cg["Reader_Org_Raw"].empty else ""

            # active individuals in the base group (count of rows / individuals)
            active_inds = cg.shape[0]
            dom = cg["Primary_Topic"].value_counts().idxmax() if cg["Primary_Topic"].notna().any() else ""
            team_signal = "Yes" if active_inds >= 2 else "No"
            beh = ", ".join(sorted(set(cg.get("Behavioral_Trigger", pd.Series(dtype=object)).dropna().astype(str).tolist())))
            ext = ""
            try:
                best = find_best_trigger_for_company(display_name)
                if best:
                    ext = best.get("external_trigger_title", "")
                else:
                    ext = ""
            except Exception:
                ext = ""
            pcs = []
            for p in cg.get("Primary_Topic", pd.Series(dtype=object)).dropna().astype(str):
                for tok in p.split(","):
                    t = tok.strip()
                    if t and t not in pcs:
                        pcs.append(t)
            prod_cat = ",".join(pcs)
            comp_rows.append({
                "Reader Org": display_name,
                "Active_Individuals": active_inds,
                "Dominant_Topic": dom,
                "Team_Buying_Signal": team_signal,
                "Behavioral_Triggers": beh,
                "External_Trigger": ext,
                "Product_Category": prod_cat,
            })
        company_combined = pd.DataFrame.from_records(comp_rows)

    # Sales hot list: prioritize high-intent / evaluation contacts
    base_hot = individuals_filtered.copy()
    if base_hot.empty:
        # fall back to all individuals if the min_engagements filter removed everything
        try:
            base_hot = deduplicate_columns(individuals_df.copy())
        except Exception:
            base_hot = individuals_df.copy()
    sales_hot = base_hot.copy()
    score_col = None
    if "Intent_Score" in sales_hot.columns:
        score_col = "Intent_Score"
    elif "Intent_Base_Score" in sales_hot.columns:
        score_col = "Intent_Base_Score"

    # Primary filter: score >= 70 when available
    if score_col:
        sales_hot = sales_hot[sales_hot[score_col].fillna(0).astype(int) >= 70]

    # Fallbacks if empty
    if sales_hot.empty:
        # Use derived/vendor evaluation stage if present
        if "Buyer_Journey_Label" in individuals_filtered.columns:
            sales_hot = individuals_filtered[individuals_filtered["Buyer_Journey_Label"] == "Vendor Evaluation"].copy()
        if sales_hot.empty and "Derived_Buyer_Journey" in individuals_filtered.columns:
            sales_hot = individuals_filtered[individuals_filtered["Derived_Buyer_Journey"] == "Vendor Evaluation"].copy()

    # Ultimate fallbacks if still empty
    if sales_hot.empty:
        source_df = base_hot if not base_hot.empty else individuals_filtered
        if score_col and score_col in source_df.columns:
            sales_hot = source_df.sort_values(score_col, ascending=False).head(50)
        elif "Total Engagements" in source_df.columns:
            sales_hot = source_df.sort_values("Total Engagements", ascending=False).head(50)
        else:
            sales_hot = source_df.head(50)
    if not sales_hot.empty:
        # Remove duplicate columns first
        sales_hot = deduplicate_columns(sales_hot)
        # adapt column names to expected Sales_Hot_List names
        sales_hot = sales_hot.rename(columns={
            "Total Engagements": "Total_Engagements",
            "Buyer_Journey_Label": "Buyer_Journey_Label",
            "Reason to Reach out": "Reason_to_Reach_Out",
        })
        # Deduplicate again after rename in case it created duplicates
        sales_hot = deduplicate_columns(sales_hot)
        # ensure column order matches v5 preview
        cols = [
            "Reader Company",
            "First Name",
            "Last Name",
            "Title",
            "Total_Engagements",
            "Buyer_Journey_Label",
            "Explanation",
            "Primary_Topic",
            "Potential_Vendors",
            "Vendors_Evaluated",
            "Buyer_Intensity_Flags",
            "Behavioral_Trigger",
            "External_Trigger (press release info, etc)",
            "Reason_to_Reach_Out",
        ]
        for c in cols:
            if c not in sales_hot.columns:
                sales_hot[c] = ""
        # Select only columns that actually exist and are unique
        existing_cols = [c for c in cols if c in sales_hot.columns]
        sales_hot = sales_hot[existing_cols].copy()
        # Final deduplication before returning
        sales_hot = deduplicate_columns(sales_hot)

    # product_map: reuse earlier approach but simpler
    product_map = pd.DataFrame(columns=["product", "mentions", "unique_companies"]) if df.empty else df.groupby("product").agg(mentions=("product", "count"), unique_companies=("reader_company", lambda s: s.dropna().nunique())).reset_index().sort_values(by="mentions", ascending=False)

    # company_summary mirrors company_combined plus additional columns
    company_summary = company_combined.copy()
    
    # Ensure all returned dataframes are deduplicated
    individuals_filtered = deduplicate_columns(individuals_filtered)

    return {
        "individuals": individuals_filtered,
        "company_combined": company_combined,
        "company_summary": company_summary,
        "product_map": product_map,
        "sales_hot_list": sales_hot,
        "raw": df,
    }


def excel_with_styles(dfs: dict, filename: str = "report.xlsx") -> bytes:
    # Writes multiple dataframes to an in-memory workbook and applies color-coding
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet, df in dfs.items():
            # Ensure company sheets use 'Reader Org' as the display column when possible
            df_to_write = df.copy()
            if sheet in ("Company_Combined", "Company_Summary"):
                # If DataFrame has 'Company' but not 'Reader Org', rename it for clarity
                if "Reader Org" not in df_to_write.columns and "Company" in df_to_write.columns:
                    df_to_write = df_to_write.rename(columns={"Company": "Reader Org"})
                # If neither present but a 'Reader_Org_Norm' exists, leave as-is
            # sanitize sheet name
            sheet_name = sheet[:31]
            df_to_write.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    wb = load_workbook(output)

    # apply coloring rules
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # find header -> find buyer_stage or stage or total_engagements
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        header_index = {h: i + 1 for i, h in enumerate(headers) if h}

        # color rows by buyer_stage or Buyer_Journey_Label column if present
        if "buyer_stage" in header_index or "Buyer_Journey_Label" in header_index:
            col_key = "buyer_stage" if "buyer_stage" in header_index else "Buyer_Journey_Label"
            col_idx = header_index[col_key]
            for row in range(2, ws.max_row + 1):
                cell = ws.cell(row=row, column=col_idx)
                stage = cell.value
                if stage in STAGE_COLOR:
                    fill = PatternFill(start_color=STAGE_COLOR[stage], end_color=STAGE_COLOR[stage], fill_type="solid")
                    cell.fill = fill

        # highlight high engagement rows (>=12) if any total engagements column present
        te_idx = None
        for key in ("total_engagements", "Total Engagements", "Total_Engagements"):
            if key in header_index:
                te_idx = header_index[key]
                break
        if te_idx:
            for row in range(2, ws.max_row + 1):
                val = ws.cell(row=row, column=te_idx).value
                try:
                    if val is not None and int(val) >= 12:
                        # apply green to the whole row
                        green = PatternFill(start_color="00C853", end_color="00C853", fill_type="solid")
                        for c in range(1, ws.max_column + 1):
                            ws.cell(row=row, column=c).fill = green
                except Exception:
                    pass

    # write back to bytes
    out2 = io.BytesIO()
    wb.save(out2)
    return out2.getvalue()


def enrich_companies_stub(companies: pd.DataFrame) -> pd.DataFrame:
    # Placeholder: integrate external trigger APIs here. Adds a column with a sample trigger flag.
    companies = companies.copy()
    companies["external_triggers"] = "(stub - no data)"
    return companies


def main():
    st.set_page_config(page_title="LSC Buyer Intelligence Web App", layout="wide")
    st.title("LSC Buyer Intelligence Web App")
    st.caption("This public version allows anyone to upload a quick-export file and generate buyer journey insights.")

    st.markdown(
        "Upload an XLSX or CSV export from Life Science Connect. The app validates columns, aggregates engagements to individuals, computes buyer journey stages, and produces an Excel report."
    )

    uploaded = st.file_uploader("Upload Life Science Connect XLSX/CSV", type=["xlsx", "csv"], accept_multiple_files=False)

    min_eng = st.sidebar.number_input("Minimum engagements per individual (filter)", value=5, min_value=1, step=1)
    enrich = st.sidebar.checkbox("Enrich high-intent companies (stub)", value=False)
    # UI option: whether to roll up company variants by their base normalized token
    rollup_base = st.sidebar.checkbox("Roll up company variants by base name (e.g. 'Abbott')", value=True)

    if uploaded is None:
        st.info("Upload a .xlsx or .csv file to begin. You can also open the sample below.")
        st.download_button("Download sample CSV", data=sample_csv(), file_name="sample_lsc_export.csv")
        return

    # Read file
    try:
        if uploaded.type == "text/csv" or uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return

    # If user provided a sandbox-style file with `User ID`, use the new
    # normalization + scoring pipeline that preserves company/title and drops PII.
    cols_lc = {c.strip().lower(): c for c in df.columns}
    if "user id" in cols_lc:
        # Normalize and remove PII
        try:
            df2 = normalize_activities_df(df)
        except Exception as e:
            st.error(f"Failed to normalize uploaded file with User ID pipeline: {e}")
            return

        # Build individuals aggregated by User ID
        groups = df2.groupby("User ID")
        indiv_records = []
        for uid, g in groups:
            # reader company: most common non-empty
            rc = ""
            try:
                rc = g["Reader Company"].dropna().astype(str).str.strip()
                rc = rc[rc != ""].mode().iloc[0] if not rc[rc != ""].empty else ""
            except Exception:
                rc = ""

            title = ""
            try:
                t = g["Title"].dropna().astype(str).str.strip()
                title = t.mode().iloc[0] if not t.empty else ""
            except Exception:
                title = ""

            total_eng = int(len(g))

            # Non-newsletter engagements heuristic
            asrc = g.get("Activity Source", pd.Series([""] * len(g))).astype(object).fillna("").astype(str)
            non_nl_mask = ~asrc.str.contains(r"\bnewsletter\b", na=False, case=False) & asrc.str.strip().ne("")
            non_nl_count = int(non_nl_mask.sum())

            last_dt = None
            if "Activity Date" in g.columns:
                try:
                    last_dt = pd.to_datetime(g["Activity Date"], errors="coerce").max()
                except Exception:
                    last_dt = None

            # Primary topic
            primary_topic = ""
            try:
                primary_topic = extract_primary_topic({
                    "content_topics": ", ".join([str(x) for x in g.get("Content Topics", []) if not pd.isna(x)]),
                    "content_title": ", ".join([str(x) for x in g.get("Content Title", []) if not pd.isna(x)]),
                    "specifics": ", ".join([str(x) for x in g.get("Specifics", []) if not pd.isna(x)]),
                })
            except Exception:
                primary_topic = ""

            vendors_eval = ""
            try:
                vendors_eval = extract_vendors_evaluated({
                    "content_source": ", ".join([str(x) for x in g.get("Content Source", []) if not pd.isna(x)]),
                    "specifics": ", ".join([str(x) for x in g.get("Specifics", []) if not pd.isna(x)]),
                    "client": ", ".join([str(x) for x in g.get("Client", []) if not pd.isna(x)]),
                    "newsletter_name": ", ".join([str(x) for x in g.get("Newsletter Name", []) if not pd.isna(x)]),
                })
            except Exception:
                vendors_eval = ""

            # Potential vendors
            pv_list = get_potential_vendors_for_topics([t.strip() for t in str(primary_topic).split(",") if t.strip()])

            # Buyer journey label (best-effort)
            bj_label = stage_from_text(primary_topic)

            indiv_records.append({
                "User ID": uid,
                "Reader Company": rc,
                "Title": title,
                "Total_Engagements": total_eng,
                "Non_NL_Engagements": non_nl_count,
                "Last_Activity_Date": last_dt,
                "Primary_Topic": primary_topic,
                "Buyer_Journey_Label": bj_label,
                "Vendors_Evaluated": vendors_eval,
                "Potential_Vendors": ", ".join(pv_list),
            })

        individuals_df = pd.DataFrame.from_records(indiv_records)
        # Remove duplicate columns if any
        individuals_df = deduplicate_columns(individuals_df)

        # Build company aggregation using normalized Reader Org (distinct user id counts)
        inds_for_agg = individuals_df.copy()
        if "Reader Org" in inds_for_agg.columns:
            inds_for_agg["Reader_Org_Raw"] = inds_for_agg["Reader Org"].astype(str).fillna("").str.strip()
        else:
            inds_for_agg["Reader_Org_Raw"] = inds_for_agg.get("Reader Company", "").astype(str).fillna("").str.strip()
        inds_for_agg["Reader_Org_Norm"] = inds_for_agg["Reader_Org_Raw"].apply(normalize_org_key)
        # choose grouping key: base token roll-up or full normalized org
        if rollup_base:
            inds_for_agg["Reader_Org_Base"] = inds_for_agg["Reader_Org_Norm"].apply(lambda x: str(x).split()[0] if str(x).strip() else "")
            agg_group_key = "Reader_Org_Base"
        else:
            agg_group_key = "Reader_Org_Norm"

        comp_agg_rows = []
        for base_key, cg in inds_for_agg.groupby(agg_group_key):
            try:
                modes = cg["Reader_Org_Raw"].mode()
                display_name = modes.iloc[0] if not modes.empty else (cg["Reader_Org_Raw"].dropna().astype(str).iloc[0] if not cg["Reader_Org_Raw"].dropna().empty else "")
            except Exception:
                display_name = cg["Reader_Org_Raw"].astype(str).iloc[0] if not cg["Reader_Org_Raw"].empty else ""
            # include a `Reader Company` column so downstream scoring (which expects
            # `Reader Company`) will use the Reader Org display name when available
            comp_agg_rows.append({"Reader Org": display_name, "Reader Company": display_name, "Company_Contact_Count": int(cg["User ID"].nunique())})
        comp_agg = pd.DataFrame.from_records(comp_agg_rows)

        # Apply intent scoring
        try:
            individuals_scored = apply_intent_scoring(individuals_df.rename(columns={"Total_Engagements": "Total_Engagements"}), comp_agg, org_column="Reader Org")
            # Remove duplicate columns from scored frame
            individuals_scored = deduplicate_columns(individuals_scored)
        except Exception as e:
            st.error(f"Failed to compute intent scoring: {e}")
            return

        # Build a company-level summary that includes team buying (Yes/No),
        # max intent, count of high-intent contacts, and best external trigger —
        # grouped by normalized Reader Org (displaying the most common original name).
        inds = individuals_scored.copy()
        if "Intent_Score" not in inds.columns and "Intent_Base_Score" in inds.columns:
            inds["Intent_Score"] = inds["Intent_Base_Score"].fillna(0).astype(int)

        # ensure Reader Org raw/norm present on scored frame
        if "Reader Org" in inds.columns:
            inds["Reader_Org_Raw"] = inds["Reader Org"].astype(str).fillna("").str.strip()
        else:
            inds["Reader_Org_Raw"] = inds.get("Reader Company", "").astype(str).fillna("").str.strip()
        inds["Reader_Org_Norm"] = inds["Reader_Org_Raw"].apply(normalize_org_key)
        if rollup_base:
            inds["Reader_Org_Base"] = inds["Reader_Org_Norm"].apply(lambda x: str(x).split()[0] if str(x).strip() else "")
            comp_grp = inds.groupby("Reader_Org_Base") if not inds.empty else []
        else:
            comp_grp = inds.groupby("Reader_Org_Norm") if not inds.empty else []

        comp_rows = []
        for base_key, cg in comp_grp:
            try:
                modes = cg["Reader_Org_Raw"].mode()
                display_name = modes.iloc[0] if not modes.empty else (cg["Reader_Org_Raw"].dropna().astype(str).iloc[0] if not cg["Reader_Org_Raw"].dropna().empty else "")
            except Exception:
                display_name = cg["Reader_Org_Raw"].astype(str).iloc[0] if not cg["Reader_Org_Raw"].empty else ""

            contact_count = int(cg["User ID"].nunique()) if "User ID" in cg.columns else int(cg.shape[0])
            max_intent = int(cg["Intent_Score"].fillna(0).astype(int).max()) if "Intent_Score" in cg.columns else 0
            num_high = int((cg.get("Intent_Score", 0) >= 60).sum()) if "Intent_Score" in cg.columns else 0

            # choose best external trigger from individuals if present
            ext_title = ""
            ext_url = ""
            ext_type = ""
            if "External_Trigger_Title" in cg.columns:
                nonempty = cg[cg["External_Trigger_Title"].astype(str).str.strip() != ""]
                if not nonempty.empty:
                    first = nonempty.iloc[0]
                    ext_title = str(first.get("External_Trigger_Title", ""))
                    ext_url = str(first.get("External_Trigger_URL", "")) if "External_Trigger_URL" in first else ""
                    ext_type = str(first.get("External_Trigger_Type", "")) if "External_Trigger_Type" in first else ""

            # If company is high-intent by max score but no individual trigger found, fetch company-level trigger
            if max_intent >= 60 and not ext_url:
                try:
                    best = find_best_trigger_for_company(display_name)
                    if best:
                        ext_title = best.get("external_trigger_title", "")
                        ext_url = best.get("external_trigger_url", "")
                        ext_type = best.get("external_trigger_type", "")
                except Exception:
                    pass

            team_buying = "Yes" if contact_count >= 2 else "No"
            high_intent_flag = "Yes" if (max_intent >= 60 or num_high >= 1) else "No"

            comp_rows.append({
                "Reader Org": display_name,
                "Company_Contact_Count": contact_count,
                "Team_Buying": team_buying,
                "Max_Intent_Score": max_intent,
                "Num_High_Intent_Contacts": num_high,
                "External_Trigger_Title": ext_title,
                "External_Trigger_URL": ext_url,
                "External_Trigger_Type": ext_type,
                "High_Intent_Flag": high_intent_flag,
            })

        company_summary = pd.DataFrame.from_records(comp_rows)

        # Build sales hot list: only include individuals with Intent_Score > 70
        if "Intent_Score" in individuals_scored.columns:
            sales_hot = individuals_scored[individuals_scored["Intent_Score"] > 70].copy()
        else:
            # no intent score available, produce empty sales hot list
            sales_hot = individuals_scored.iloc[0:0].copy()

        # Rename back to display name and ensure no duplicates
        result_inds = individuals_scored.copy()
        if "Total_Engagements" in result_inds.columns:
            result_inds = result_inds.drop(columns=["Total Engagements"], errors="ignore")  # Remove old name if exists
            result_inds = result_inds.rename(columns={"Total_Engagements": "Total Engagements"})
        result_inds = deduplicate_columns(result_inds)

        results = {
            "individuals": result_inds,
            "company_combined": comp_agg,  # already contains 'Reader Org' & counts
            "company_summary": company_summary,
            "product_map": pd.DataFrame(),
            "sales_hot_list": sales_hot,
            "raw": df2,
        }

    else:
        # Normalize columns immediately after upload and show normalized column list for debugging
        try:
            df = normalize_columns(df)
        except ValueError as e:
            st.error(str(e))
            st.write("Columns found:", list(df.columns))
            return

    # Remove legacy 'Buyer_Journey_Label' from results to avoid showing the old label
    # Prefer derived or original intent-based labels instead.
    try:
        for k in ("individuals", "sales_hot_list", "company_combined", "company_summary"):
            if k in locals():
                pass
        if 'results' in locals() and isinstance(results, dict):
            for key in ("individuals", "sales_hot_list", "company_combined", "company_summary"):
                df_k = results.get(key)
                if df_k is not None and hasattr(df_k, 'columns') and 'Buyer_Journey_Label' in df_k.columns:
                    results[key] = df_k.drop(columns=['Buyer_Journey_Label'])
    except Exception:
        # non-fatal: continue without removal if something unexpected occurs
        pass

    # Show normalized columns in a collapsed expander by default to reduce UI clutter
    with st.expander("Normalized Columns (click to expand)", expanded=False):
        st.write(list(df.columns))

    # Process (legacy pipeline if not using User ID)
    if "user id" not in cols_lc:
        with st.spinner("Processing data — this may take a moment for tens of thousands of rows..."):
            results = process_dataframe(df, min_engagements=min_eng, rollup_base=rollup_base)

    st.success("Processing complete")

    # Show previews
    # Build display-time filters in the sidebar. These only affect what is shown
    # in the app UI; the generated Excel file remains unchanged and uses the
    # original `results` values.
    inds_all = results["individuals"].copy()

    # Sidebar controls
    st.sidebar.markdown("**Display filters (UI only)**")
    lifecycle_selection = st.sidebar.multiselect(
        "Drug Development Lifecycle Stage",
        options=list(LIFECYCLE_CATEGORIES.keys()),
        format_func=lambda k: LIFECYCLE_CATEGORIES[k],
        help="Filter by where the company is in the drug development and manufacturing lifecycle.",
        key="lifecycle_stage",
    )

    # Product / topic options - stage-aware and pruned to topics present in data
    existing_topics = set()
    if not inds_all.empty:
        for col in ["Primary_Topic", "Primary Topic", "Product_Category"]:
            if col in inds_all.columns:
                series_vals = inds_all[col].dropna().astype(str)
                for s in series_vals:
                    for t in str(s).split(","):
                        tt = t.strip()
                        if tt:
                            existing_topics.add(tt)

    topic_options = get_topics_for_lifecycle(lifecycle_selection, existing_topics=sorted(existing_topics))
    selected_topics = st.sidebar.multiselect(
        "Products / Topics of Interest",
        options=topic_options,
        default=[],
        help="Filter by specific products, technologies, or topics.",
        key="topic_filter",
    )

    # External trigger type filter
    trigger_type_options = ["funding", "expansion", "hires", "partnership", "press", "merger", "regulatory"]
    selected_trigger_types = st.sidebar.multiselect(
        "External Trigger Types",
        options=trigger_type_options,
        default=[],
        help="Filter by type of external news/events (funding, expansion, hires, etc.).",
        key="trigger_type_filter",
    )

    # Determine which column to use for topics
    topic_column = None
    for col in ["Primary_Topic", "Primary Topic", "Product_Category"]:
        if col in inds_all.columns:
            topic_column = col
            break

    # Debug: show which column is being used
    if lifecycle_selection or selected_topics:
        st.sidebar.caption(f"Using column: {topic_column if topic_column else 'None found'}")

    # Apply lifecycle/topic filters first
    if topic_column:
        inds_base = apply_lifecycle_topic_filters(
            inds_all,
            lifecycle_column=topic_column,
            topic_column=topic_column,
            selected_lifecycles=lifecycle_selection,
            selected_topics=selected_topics,
        )
    else:
        inds_base = inds_all.copy()
    # Show filter counts for debugging
    if lifecycle_selection or selected_topics:
        st.sidebar.markdown(f"**Lifecycle/Topic filtered:** {len(inds_base):,} of {len(inds_all):,} individuals")


    # Apply external trigger type filter
    if selected_trigger_types and "External_Trigger_Type" in inds_base.columns:
        trigger_mask = pd.Series(False, index=inds_base.index)
        for ttype in selected_trigger_types:
            trigger_mask |= inds_base["External_Trigger_Type"].astype(str).str.contains(ttype, case=False, na=False)
        inds_base = inds_base[trigger_mask].copy()
    st.sidebar.markdown(f"**After trigger filter:** {len(inds_base):,} individuals")

    label_col = "Buyer_Journey_Label"

    if not inds_base.empty:
        # Gather potential vendors and evaluated vendors as option lists
        pv_series = inds_base.get("Potential_Vendors", pd.Series(dtype=object)).dropna().astype(str)
        pv_options = sorted({v.strip() for s in pv_series for v in s.split(",") if v.strip()})
        ev_series = inds_base.get("Vendors_Evaluated", pd.Series(dtype=object)).dropna().astype(str)
        ev_options = sorted({v.strip() for s in ev_series for v in s.split(",") if v.strip()})

        # Use session_state keys so we can reset the widgets programmatically
        selected_pv = st.sidebar.multiselect("Potential Vendors", options=pv_options, default=[], key="pv")
        selected_ev = st.sidebar.multiselect("Vendors Evaluated", options=ev_options, default=[], key="ev")

        max_eng = int(inds_base["Total Engagements"].max()) if "Total Engagements" in inds_base.columns and not inds_base["Total Engagements"].isnull().all() else 20
        min_eng_display = st.sidebar.slider("Min engagements to display", 1, max(1, max_eng), value=int(min_eng), key="min_eng_display")

        top_n = st.sidebar.slider("Top N engaged people (0 = off)", 0, 50, 0, key="top_n")
        only_vendor_eval = st.sidebar.checkbox("Only Vendor Evaluation stage", value=False, key="only_vendor_eval")
        # allow user to prefer the intent-derived buyer journey when available
        prefer_derived_stage = st.sidebar.checkbox("Prefer stage from intent (derived)", value=True, key="prefer_derived_stage")

        # Reset filters button: clears UI-only selections (does not affect Excel export)
        if st.sidebar.button("Reset filters"):
            st.session_state["pv"] = []
            st.session_state["ev"] = []
            st.session_state["min_eng_display"] = int(min_eng)
            st.session_state["top_n"] = 0
            st.session_state["only_vendor_eval"] = False
            st.session_state["lifecycle_stage"] = []
            st.session_state["topic_filter"] = []
            st.session_state["trigger_type_filter"] = []

        # Apply filters to a display copy
        filt = pd.Series(True, index=inds_base.index)
        if selected_pv:
            pv_mask = pd.Series(False, index=inds_base.index)
            for v in selected_pv:
                pv_mask |= inds_base.get("Potential_Vendors", pd.Series("", index=inds_base.index)).astype(object).fillna("").astype(str).str.contains(re.escape(v), case=False, na=False)
            filt &= pv_mask
        if selected_ev:
            ev_mask = pd.Series(False, index=inds_base.index)
            for v in selected_ev:
                ev_mask |= inds_base.get("Vendors_Evaluated", pd.Series("", index=inds_base.index)).astype(object).fillna("").astype(str).str.contains(re.escape(v), case=False, na=False)
            filt &= ev_mask

        if min_eng_display:
            if "Total Engagements" in inds_base.columns:
                filt &= inds_base["Total Engagements"] >= int(min_eng_display)

        # respect user's preference for which Buyer Journey label to use
        if prefer_derived_stage:
            label_col = "Buyer_Journey_Label_Derived" if "Buyer_Journey_Label_Derived" in inds_base.columns else "Buyer_Journey_Label"
        else:
            label_col = "Buyer_Journey_Label"

        if only_vendor_eval:
            if label_col in inds_base.columns:
                filt &= inds_base[label_col] == "Vendor Evaluation"

        inds_filtered = inds_base[filt].copy()
        if top_n and top_n > 0 and "Total Engagements" in inds_filtered.columns:
            inds_filtered = inds_filtered.sort_values("Total Engagements", ascending=False).head(top_n)
    else:
        inds_filtered = inds_all
    # Show final count
    st.sidebar.markdown(f"**Final display:** {len(inds_filtered):,} individuals")


    # UI: simplified view toggle and highlighted indicators
    # provide a compact/simple view toggle in the sidebar
    try:
        simple_view = st.sidebar.checkbox("Simple view (compact)", value=True, key="simple_view")
    except Exception:
        simple_view = True
    st.subheader("Individuals (filtered)")
    # Field definitions / tooltips: provide an expandable reference for non-obvious fields
    with st.expander("Field definitions (click to expand)"):
        st.markdown("""
        - **Intent_Score:** A combined score (0–100) based on engagement frequency, recency, non-NL weight, buyer journey behavior, vendor evaluation depth, and external triggers.
        - **Confidence_Score:** A metric indicating how reliable the intent score is, based on activity recency, non-NL engagement weight, and the availability of external triggers.
        - **Derived_Buyer_Journey_Label:** The inferred stage of the buyer: Awareness → Solution Exploration → Problem Definition → Vendor Evaluation → Active Purchase.
        - **Vendor_Intensity_Flags / Buyer_Intensity_Flags:** Signals based on non-NL engagement, depth of comparison activity, and repeat visits to product-specific content.
        - **External_Trigger_Type:** Press-driven indicators such as funding, expansion, new hires, or major partnerships.
        """)
        # second expander: exact formulas and weights
        with st.expander("Formulas & Weights (click to expand)"):
            st.markdown("""
            **Intent_Score (how it's computed)**
            - Compute intermediate components:
              - `recency_score`: 3 (<=30 days), 2 (<=90d), 1 (<=180d), 0 (older/unknown)
              - `engagement_score`: `Total_Engagements` (capped at 30) + `Non_NL_Engagements`
              - `buyer_journey_base`: mapping {Awareness:5, Solution Exploration:10, Problem Definition:15, Vendor Evaluation:20}
              - `team_buying_score`: 5 if company contacts >=3, 3 if ==2, else 0
              - `vendor_eval_score`: 5 if vendors evaluated >=5, 3 if 2-4, else 0
            - `raw_base_score` = engagement_score + recency_score + buyer_journey_base + team_buying_score + vendor_eval_score
            - `Intent_Base_Score` = linear scale of `raw_base_score` to 0-100 across the dataset (min→0, max→100)
            - `Intent_Score` = `Intent_Base_Score` + `External_Trigger_Score` (capped at 100)

            **Confidence_Score (how it's computed)**
            - Start at 0; add:
              - +30 if last activity <= 90 days
              - +30 if `Non_NL_Engagements` >= 3
                                    - +40 if `External_Trigger_Score` > 0
                                - Final: clipped to 0-100

                                **Derived_Buyer_Journey_Label (thresholds & hybrid rule)**
                                - Derived from `Intent_Score`:
                                    - >=81 → High-Priority Hot Lead
                                    - 61–80 → Vendor Evaluation
                                    - 41–60 → Solution Exploration
                                    - 21–40 → Problem Definition
                                    - 0–20 → Awareness
                                - Hybrid escalation rule: if `Intent_Score` < 61 but (`Non_NL_Engagements` >= 3 OR `Vendors_Evaluated` count >= 2), promote to `Vendor Evaluation`.

                                **Vendor_Intensity_Flags / Buyer_Intensity_Flags (heuristics)**
                                - Flags set by `detect_behavioral_triggers_and_flags` using:
                                    - explicit `activity_source` non-newsletter markers → mark Non-NL engagement
                                    - late-stage keywords in content (compare/pricing/quote/RFP/vendor/evaluation) → Late-stage content flag
                                    - process keywords (upstream/downstream/scale-up/tech transfer/viral clearance/etc.) counted >=2 → Deep process interest

                                **External_Trigger_Type (how it's inferred)**
                                - Articles fetched via NewsAPI or Google News RSS are classified by keyword rules into types like `funding`, `expansion`, `hires`, `partnership`, or `press` and assigned an `External_Trigger_Score` which is added to `Intent_Score`.

                                """)
        def priority_emoji(row):
            s = row.get("Intent_Score") if row is not None else None
            try:
                s = int(s)
            except Exception:
                s = None
            if s is None:
                return ""
            if s >= 85:
                return "🔥🔥"
            if s >= 70:
                return "🔥"
            if s >= 50:
                return "⚡"
            return ""

    # prepare display frame from filtered individuals
    try:
        disp = inds_filtered.copy()
    except Exception:
        disp = pd.DataFrame()

    if not disp.empty:
        disp["Priority"] = disp.apply(priority_emoji, axis=1)

    if 'simple_view' not in locals():
        simple_view = True
    if simple_view:
        # prefer display of Reader Org if present
        preferred_org_col = "Reader Org" if "Reader Org" in disp.columns else "Reader Company"
        cols_base = ["Priority", "User ID", preferred_org_col, "Title", "Total Engagements"]
        # include the chosen label column (derived) or the display alias
        label_display = "Derived_Buyer_Journey_Label" if "Derived_Buyer_Journey_Label" in disp.columns else label_col
        cols_rest = [label_display, "Primary_Topic", "Potential_Vendors", "Vendors_Evaluated", "External_Trigger_Title", "External_Trigger_URL", "Intent_Score", "Intent_Label", "Confidence_Score"]
        show_cols = [c for c in (cols_base + cols_rest) if c in disp.columns]
        disp_show = deduplicate_columns(disp[show_cols].copy())
        st.dataframe(disp_show.head(200))
        with st.expander("Advanced: show all columns"):
            st.dataframe(deduplicate_columns(disp.copy()).head(200))
    else:
        st.dataframe(deduplicate_columns(disp.copy()).head(200))

    # Top insights: highlight companies with high intent and external triggers
    st.markdown("**Top Insights**")
    try:
        comp_sum = results.get("company_summary")
        if comp_sum is not None and not comp_sum.empty:
            # prefer 'Reader Org' for display if present
            display_col = "Reader Org" if "Reader Org" in comp_sum.columns else ("Company" if "Company" in comp_sum.columns else comp_sum.columns[0])
            top_comp = comp_sum.sort_values(by=["Max_Intent_Score"], ascending=False).head(10)
            for _, r in top_comp.iterrows():
                title = r.get(display_col, "")
                score = r.get("Max_Intent_Score", "")
                ext_title = r.get("External_Trigger_Title", "")
                ext_url = r.get("External_Trigger_URL", "")
                line = f"- **{title}** — Intent: {score}"
                if ext_title and ext_url:
                    line += f" — [{ext_title}]({ext_url})"
                elif ext_title:
                    line += f" — {ext_title}"
                st.markdown(line)
    except Exception:
        pass

    st.subheader("Company Summary")
    company_summary = deduplicate_columns(results["company_summary"].copy())
    st.dataframe(company_summary.head(200))

    st.subheader("Sales Hot List")
    # Sales Hot List: use the prefiltered list; do not re-filter here to avoid emptying
    sh = results.get("sales_hot_list", pd.DataFrame()).copy()
    sh = deduplicate_columns(sh)
    st.caption(f"Sales Hot List rows: {len(sh)}")
    st.dataframe(sh.head(200))
    with st.expander("Sales Hot List debug (counts)"):
        inds_dbg = results.get("individuals", pd.DataFrame())
        st.write({
            "individuals_rows": len(inds_dbg),
            "sales_hot_rows": len(sh),
            "has_intent_score": "Intent_Score" in inds_dbg.columns,
            "has_intent_base_score": "Intent_Base_Score" in inds_dbg.columns,
            "has_bj_label": "Buyer_Journey_Label" in inds_dbg.columns,
            "has_derived_bj": "Derived_Buyer_Journey" in inds_dbg.columns,
        })
        if not inds_dbg.empty:
            counts = {}
            if "Intent_Score" in inds_dbg.columns:
                counts["Intent_Score>=70"] = int((inds_dbg["Intent_Score"].fillna(0).astype(int) >= 70).sum())
            if "Buyer_Journey_Label" in inds_dbg.columns:
                counts["Vendor_Eval_Label"] = int((inds_dbg["Buyer_Journey_Label"] == "Vendor Evaluation").sum())
            if "Derived_Buyer_Journey" in inds_dbg.columns:
                counts["Vendor_Eval_Derived"] = int((inds_dbg["Derived_Buyer_Journey"] == "Vendor Evaluation").sum())
            st.write(counts)

    # optional enrichment
    if enrich:
        with st.spinner("Running enrichment (stub)..."):
            enriched = enrich_companies_stub(results["company_summary"])  # placeholder
            st.write(enriched.head(50))
            results["company_summary"] = enriched

    # Prepare Excel
    sheets = {
        "Company_Combined": results["company_combined"],
        "Company_Summary": results["company_summary"],
        "Individuals": results["individuals"],
        "Product_Map": results["product_map"],
        "Sales_Hot_List": results["sales_hot_list"],
    }

    excel_bytes = excel_with_styles(sheets, filename="LSC_Buyer_Journey_Report.xlsx")

    st.download_button(label="Download Excel Report", data=excel_bytes, file_name="LSC_Buyer_Journey_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def sample_csv() -> bytes:
    sample = pd.DataFrame(
        {
            "First Name": ["Alice", "Bob"],
            "Last Name": ["A", "B"],
            "Email": ["alice@example.com", "bob@example.com"],
            "Reader Company": ["Acme Inc", "Beta LLC"],
            "Activity Date": [datetime.now().isoformat(), datetime.now().isoformat()],
            "Activity Source": ["webinar - product features", "requested demo"],
            "Content Title": ["Webinar: Product X Features", "Requested Demo for Product Y"],
            "Product": ["Product X", "Product Y"],
        }
    )
    return sample.to_csv(index=False).encode("utf-8")


if __name__ == "__main__":
    main()
