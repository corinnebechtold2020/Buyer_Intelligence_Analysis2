from typing import List
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

from external_triggers import find_best_trigger_for_company


def compute_base_intent(individuals_df: pd.DataFrame, company_agg_df: pd.DataFrame) -> pd.DataFrame:
    df = individuals_df.copy()
    today = pd.Timestamp.now().normalize()

    # ensure expected columns
    for c in ["Last_Activity_Date", "Total_Engagements", "Non_NL_Engagements", "Buyer_Journey_Label", "Vendors_Evaluated", "Reader Company"]:
        if c not in df.columns:
            df[c] = np.nan

    # recency score
    def recency_score(last):
        try:
            if pd.isna(last):
                return 0
            days = (today - pd.to_datetime(last)).days
        except Exception:
            return 0
        if days <= 30:
            return 3
        if days <= 90:
            return 2
        if days <= 180:
            return 1
        return 0

    df["recency_score"] = df["Last_Activity_Date"].apply(recency_score)

    # engagement score
    df["engagement_score"] = df["Total_Engagements"].fillna(0).astype(int).clip(upper=30) + df["Non_NL_Engagements"].fillna(0).astype(int)

    # buyer journey base
    mapping = {
        "Awareness": 5,
        "Solution Exploration": 10,
        "Problem Definition": 15,
        "Vendor Evaluation": 20,
    }
    df["buyer_journey_base"] = df["Buyer_Journey_Label"].map(mapping).fillna(0).astype(int)

    # team buying
    # company_agg_df expected to have Reader Company and Company_Contact_Count
    comp_counts = {}
    if company_agg_df is not None and "Reader Company" in company_agg_df.columns:
        for _, r in company_agg_df.iterrows():
            comp_counts[r["Reader Company"]] = int(r.get("Company_Contact_Count", 0))

    def team_buying_score(rc):
        cnt = comp_counts.get(rc, 0)
        if cnt >= 3:
            return 5
        if cnt == 2:
            return 3
        return 0

    df["team_buying_score"] = df["Reader Company"].apply(team_buying_score)

    # vendor evaluation depth
    def vendor_eval_score(vs):
        if not vs or (isinstance(vs, float) and pd.isna(vs)):
            return 0
        if isinstance(vs, (list, tuple)):
            n = len(vs)
        else:
            # assume comma-separated
            n = len([s for s in str(vs).split(",") if s.strip()])
        if n >= 5:
            return 5
        if 2 <= n <= 4:
            return 3
        return 0

    df["vendor_eval_score"] = df["Vendors_Evaluated"].apply(vendor_eval_score)

    # raw base score
    df["raw_base_score"] = df["engagement_score"] + df["recency_score"] + df["buyer_journey_base"] + df["team_buying_score"] + df["vendor_eval_score"]

    # Normalize to 0-100 by scaling: find min/max and scale linearly
    min_raw = df["raw_base_score"].min() if not df.empty else 0
    max_raw = df["raw_base_score"].max() if not df.empty else 1
    if max_raw == min_raw:
        df["Intent_Base_Score"] = df["raw_base_score"].apply(lambda x: int(np.clip(x, 0, 100)))
    else:
        df["Intent_Base_Score"] = df["raw_base_score"].apply(lambda x: int(np.clip((x - min_raw) / (max_raw - min_raw) * 100, 0, 100)))

    # Labels
    def intent_label(s):
        if s <= 20:
            return "Awareness"
        if s <= 40:
            return "Solution Exploration"
        if s <= 60:
            return "Vendor Evaluation"
        if s <= 80:
            return "Active Purchase"
        return "High-Priority Hot Lead"

    df["Intent_Base_Label"] = df["Intent_Base_Score"].apply(intent_label)

    # Remove intermediate/debug columns before returning
    drop_cols = ["recency_score", "engagement_score", "buyer_journey_base", "team_buying_score", "vendor_eval_score", "raw_base_score"]
    for c in drop_cols:
        if c in df.columns:
            df = df.drop(columns=[c], errors="ignore")

    return df


def enrich_with_external_triggers(individuals_df: pd.DataFrame) -> pd.DataFrame:
    df = individuals_df.copy()
    df["External_Trigger_Title"] = ""
    df["External_Trigger_URL"] = ""
    df["External_Trigger_Type"] = ""
    df["External_Trigger_Score"] = 0

    # Only call external triggers for companies with base score >= 60
    for idx, row in df.iterrows():
        try:
            base = int(row.get("Intent_Base_Score", 0))
        except Exception:
            base = 0
        if base >= 60:
            comp = row.get("Reader Company", "")
            if not comp:
                continue
            best = find_best_trigger_for_company(comp)
            if best:
                df.at[idx, "External_Trigger_Title"] = best.get("external_trigger_title", "")
                df.at[idx, "External_Trigger_URL"] = best.get("external_trigger_url", "")
                df.at[idx, "External_Trigger_Type"] = best.get("external_trigger_type", "")
                df.at[idx, "External_Trigger_Score"] = int(best.get("external_trigger_score", 0))

    # Final Intent_Score
    df["Intent_Score"] = (df["Intent_Base_Score"].fillna(0).astype(int) + df["External_Trigger_Score"].fillna(0).astype(int)).clip(upper=100)
    df["Intent_Score"] = df["Intent_Score"].astype(int)

    # Intent label
    def intent_label(s):
        if s <= 20:
            return "Awareness"
        if s <= 40:
            return "Solution Exploration"
        if s <= 60:
            return "Vendor Evaluation"
        if s <= 80:
            return "Active Purchase"
        return "High-Priority Hot Lead"

    df["Intent_Label"] = df["Intent_Score"].apply(intent_label)

    # Confidence score
    def compute_confidence(row):
        conf = 0
        try:
            last = row.get("Last_Activity_Date")
            if not pd.isna(last):
                days = (pd.Timestamp.now().normalize() - pd.to_datetime(last)).days
            else:
                days = 9999
        except Exception:
            days = 9999
        if days <= 90:
            conf += 30
        if int(row.get("Non_NL_Engagements", 0)) >= 3:
            conf += 30
        if int(row.get("External_Trigger_Score", 0)) > 0:
            conf += 40
        return int(max(0, min(100, conf)))

    df["Confidence_Score"] = df.apply(compute_confidence, axis=1)

    # Hybrid-derived Buyer Journey: preserve original and add a derived stage
    def derive_from_intent(score: int) -> str:
        if score >= 81:
            return "High-Priority Hot Lead"
        if score >= 61:
            return "Vendor Evaluation"
        if score >= 41:
            return "Solution Exploration"
        if score >= 21:
            return "Problem Definition"
        return "Awareness"

    # compute vendor evaluation depth numeric if possible
    def vendors_count(vs):
        if not vs or (isinstance(vs, float) and pd.isna(vs)):
            return 0
        if isinstance(vs, (list, tuple)):
            return len(vs)
        return len([s for s in str(vs).split(",") if s.strip()])

    df["Original_Buyer_Journey"] = df.get("Buyer_Journey_Label", "")
    df["Derived_Buyer_Journey"] = df["Intent_Score"].fillna(0).astype(int).apply(derive_from_intent)

    # Hybrid escalation rules: promote to Vendor Evaluation when strong signals exist
    for idx, row in df.iterrows():
        try:
            intent = int(row.get("Intent_Score", 0))
        except Exception:
            intent = 0
        non_nl = int(row.get("Non_NL_Engagements", 0)) if "Non_NL_Engagements" in df.columns else 0
        vcount = vendors_count(row.get("Vendors_Evaluated", "")) if "Vendors_Evaluated" in df.columns else 0

        # If intent is high, keep derived mapping; otherwise escalate when evidence present
        if intent < 61:
            if non_nl >= 3 or vcount >= 2:
                df.at[idx, "Derived_Buyer_Journey"] = "Vendor Evaluation"

    # final: return dataframe with derived stage included
    return df


def apply_intent_scoring(individuals_df: pd.DataFrame, company_agg_df: pd.DataFrame) -> pd.DataFrame:
    base = compute_base_intent(individuals_df, company_agg_df)
    enriched = enrich_with_external_triggers(base)
    return enriched
