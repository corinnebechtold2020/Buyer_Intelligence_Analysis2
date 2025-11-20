from typing import List

PRODUCT_VENDOR_MAP = {
    "Downstream Isolation And Purification": [
        "Cytiva", "Sartorius", "Tosoh Bioscience", "Bio-Rad",
        "Thermo Fisher Scientific", "Repligen", "Purolite Resins",
        "Asahi Kasei Bioprocess", "MilliporeSigma", "3M Health Care"
    ],
    "Upstream Cell Culture And Fermentation": [
        "Thermo Fisher Scientific", "Cytiva", "Sartorius",
        "Fujifilm Irvine Scientific", "Eppendorf", "PBS Biotech",
        "Corning Life Sciences", "INFORS HT"
    ],
    "Bioprocess Manufacturing Controls": [
        "Emerson Automation Solutions", "Blue Mountain", "ValGenesis",
        "Siemens", "Honeywell", "Rockwell Automation",
        "Cytiva", "Sartorius"
    ],
    "Bioprocess Analytical Methods": [
        "Waters", "Agilent", "SCIEX", "Shimadzu", "Bruker", "Phenomenex",
        "Thermo Fisher Scientific"
    ],
    "QA/QC": [
        "Waters", "Agilent", "Bio-Rad", "Thermo Fisher Scientific",
        "Shimadzu", "Bruker", "TSI", "Particle Measuring Systems"
    ],
    "Cell Therapy Manufacturing": [
        "GE Healthcare", "Miltenyi Biotec", "Thermo Fisher Scientific", "Cytiva",
        "Sartorius", "Lonza"
    ],
    "CMO CDMO": [
        "Lonza", "Catalent", "Samsung Biologics", "WuXi Biologics", "Thermo Fisher Scientific",
        "Boehringer Ingelheim", "Sartorius"
    ],
}


def get_potential_vendors_for_topics(topics: List[str]) -> List[str]:
    """Return a unique combined list of vendors for given topics."""
    vendors = []
    for t in topics:
        if not t:
            continue
        # match by exact key or case-insensitive contains
        t_norm = t.strip()
        # direct match
        if t_norm in PRODUCT_VENDOR_MAP:
            vendors.extend(PRODUCT_VENDOR_MAP[t_norm])
            continue
        # fuzzy contains
        for key, vs in PRODUCT_VENDOR_MAP.items():
            if t_norm.lower() in key.lower() or key.lower() in t_norm.lower():
                vendors.extend(vs)

    # unique preserving order
    seen = set()
    out = []
    for v in vendors:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
