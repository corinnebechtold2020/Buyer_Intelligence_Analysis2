import pandas as pd
from typing import Iterable, List

LIFECYCLE_CATEGORIES = {
    "discovery_screening": "Discovery & Screening",
    "preclinical": "Preclinical Development",
    "process_development": "Process Development",
    "clinical_manufacturing": "Clinical Manufacturing",
    "commercial_manufacturing": "Commercial Manufacturing",
    "cmc_reg_quality": "CMC / Regulatory / Quality",
    "outsourcing_cdmo": "Outsourcing / CDMO / Partnerships",
}

LIFECYCLE_TO_TOPICS = {
    "discovery_screening": [
        "Target Discovery",
        "High-Throughput Screening",
        "Lead Optimization",
        "Early Analytical Methods",
        "Assay Development",
    ],
    "preclinical": [
        "In Vitro Models",
        "In Vivo Models",
        "Toxicology",
        "Preclinical Assays",
        "ADME",
        "PK/PD",
    ],
    "process_development": [
        "Upstream Cell Culture And Fermentation",
        "Upstream Cell Line Development",
        "Upstream Cell Expansion",
        "Media Optimization",
        "Bioreactors",
        "Process Development",
        "Downstream Isolation And Purification",
        "Downstream Polish And Viral Clearance",
        "Chromatography",
        "Filtration",
        "Bioprocess Analytical Methods",
        "Scale-up",
        "Tech Transfer",
        "MSAT",
        "Process Characterization",
        "Design of Experiments",
    ],
    "clinical_manufacturing": [
        "Manufacturing",
        "GMP Manufacturing",
        "Clinical Manufacturing",
        "Single-Use Technologies",
        "In-Process Testing",
        "Facility Design",
        "Bioprocess Facility Design",
        "QA/QC",
        "Validation",
        "Raw Material Qualification",
        "Contamination Control",
        "Environmental Monitoring",
        "Process Validation",
    ],
    "commercial_manufacturing": [
        "Commercial Manufacturing",
        "Large-Scale Bioreactors",
        "Process Intensification",
        "Bioprocess Manufacturing Controls",
        "Pharmaceutical Manufacturing Controls",
        "Automation",
        "MES",
        "Digital Manufacturing",
        "Real-Time Release Testing",
        "Continued Process Verification",
        "Capacity Expansion",
    ],
    "cmc_reg_quality": [
        "CMC",
        "Regulatory",
        "Regulatory Submissions",
        "Stability",
        "Release Testing",
        "Quality Assurance",
        "Quality Control",
        "Analytical Development",
    ],
    "outsourcing_cdmo": [
        "CMO-CDMO",
        "Contract Pharma Manufacturing (OUTPH)",
        "Outsourcing",
        "CDMO Selection",
        "Tech Transfer Support",
        "Process Characterization",
        "Comparability Studies",
        "Vendor Evaluation",
    ],
}


def _split_topic_cell(val: str) -> List[str]:
    if val is None or pd.isna(val):
        return []
    parts = [p.strip() for p in str(val).split(",") if p.strip()]
    return parts if parts else [str(val).strip()] if str(val).strip() else []


def get_topics_for_lifecycle(selected_lifecycles, existing_topics: Iterable[str] | None = None) -> List[str]:
    """
    Return a sorted list of topics relevant to the selected lifecycle stages.
    - If lifecycles are selected: union of topics for those stages.
    - If none selected: all topics across stages.
    - If existing_topics provided: intersect with the available topics in data to avoid showing options that are absent.
    """
    topics = set()
    if selected_lifecycles:
        for lc in selected_lifecycles:
            topics.update(LIFECYCLE_TO_TOPICS.get(lc, []))
    else:
        for topic_list in LIFECYCLE_TO_TOPICS.values():
            topics.update(topic_list)

    if existing_topics:
        existing = {t.strip() for t in existing_topics if isinstance(t, str)}
        topics = topics.intersection(existing) or topics  # fall back to mapped topics if intersection is empty

    return sorted(topics)


def apply_lifecycle_topic_filters(
    df: pd.DataFrame,
    lifecycle_column: str,
    topic_column: str,
    selected_lifecycles: List[str],
    selected_topics: List[str],
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    filtered = df.copy()

    lifecycle_topics = set()
    if selected_lifecycles:
        for lc in selected_lifecycles:
            lifecycle_topics.update(LIFECYCLE_TO_TOPICS.get(lc, []))

    def topic_matches(cell: str, candidates: set[str]) -> bool:
        if not candidates:
            return True
        topics = set(_split_topic_cell(cell))
        return bool(topics.intersection(candidates))

    if lifecycle_topics:
        filtered = filtered[filtered[topic_column].astype(str).apply(lambda x: topic_matches(x, lifecycle_topics))]

    if selected_topics:
        topics_set = set(selected_topics)
        filtered = filtered[filtered[topic_column].astype(str).apply(lambda x: topic_matches(x, topics_set))]

    return filtered
