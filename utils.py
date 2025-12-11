import pandas as pd
import numpy as np


def normalize_activities_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize incoming activities export for analysis.

    Expects (at least) columns like:
    "User ID", "Reader Company", "Title", "Activity Date",
    "Content Title", "Content Topics", "Content Buyer's Journey",
    "Activity Source", "Specifics", "Client", "Newsletter Name"

    Behavior:
    - Keep: User ID, Reader Company, Title and behavior columns
    - Drop obvious PII: First Name, Last Name, Email, Address, City, State, Zip
    - Ensure Activity Date -> datetime
    - Strip whitespace from string columns
    - Ensure optional columns exist (Newsletter Name, Client)
    - Return DataFrame without PII columns
    """

    df = df.copy()

    # Normalize column names to common variants (case-insensitive)
    col_map = {}
    for c in df.columns:
        lc = c.strip()
        col_map[c] = lc

    # canonical names we will use
    canonical = {
        "user id": "User ID",
        "userid": "User ID",
        "reader company": "Reader Company",
        "company": "Reader Company",
        "company name": "Reader Company",
        "title": "Title",
        "activity date": "Activity Date",
        "activity_date": "Activity Date",
        "content title": "Content Title",
        "content_title": "Content Title",
        "content topics": "Content Topics",
        "content_topics": "Content Topics",
        "content buyer's journey": "Content Buyer's Journey",
        "content_bj_label": "Content Buyer's Journey",
        "activity source": "Activity Source",
        "specifics": "Specifics",
        "client": "Client",
        "newsletter name": "Newsletter Name",
        "newsletter_name": "Newsletter Name",
    }

    rename_map = {}
    for orig in df.columns:
        key = orig.strip().lower()
        if key in canonical:
            rename_map[orig] = canonical[key]

    if rename_map:
        df = df.rename(columns=rename_map)

    # Ensure required behavior columns exist; if missing, create empty
    required_optional = ["Content Title", "Content Topics", "Content Buyer's Journey", "Activity Source", "Specifics", "Client", "Newsletter Name"]
    for c in required_optional:
        if c not in df.columns:
            df[c] = ""

    # Convert Activity Date to datetime
    if "Activity Date" in df.columns:
        df["Activity Date"] = pd.to_datetime(df["Activity Date"], errors="coerce")

    # Strip whitespace from object/string columns
    obj_cols = df.select_dtypes(include=[object]).columns.tolist()
    for c in obj_cols:
        df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)

    # Convert common repeated string columns to categorical to save memory and speed groupby
    for c in ("Reader Company", "Title", "Activity Source", "Content Topics", "Newsletter Name", "Client"):
        if c in df.columns:
            try:
                # ensure missing values are represented and included in categories
                df[c] = df[c].astype(object).fillna("").astype(str)
                df[c] = df[c].astype("category")
            except Exception:
                pass

    # Drop obvious PII
    pii_candidates = [c for c in df.columns if c.strip().lower() in ("first name", "first_name", "lastname", "last name", "last_name", "email", "address", "city", "state", "zip", "zipcode", "postalcode")]
    df = df.drop(columns=[c for c in pii_candidates if c in df.columns], errors="ignore")

    # Ensure User ID exists (may be missing in older files)
    if "User ID" not in df.columns:
        # As fallback create surrogate id per row
        df["User ID"] = (pd.Series(range(1, len(df) + 1)).astype(str)).values

    # Ensure Reader Company and Title exist
    if "Reader Company" not in df.columns:
        df["Reader Company"] = ""
    if "Title" not in df.columns:
        df["Title"] = ""

    # Final: remove columns with obvious PII remaining by name pattern
    for p in ["first", "last", "email", "address", "zip", "phone"]:
        drop_cols = [c for c in df.columns if p in c.lower() and c not in ("Primary_Topic",)]
        for dc in drop_cols:
            # avoid dropping columns like 'company_email_domain'
            if dc in df.columns and dc.lower() in ("first name", "last name", "email", "address", "city", "state", "zip"):
                df = df.drop(columns=[dc], errors="ignore")

    return df
