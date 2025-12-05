from typing import List

# Comprehensive product → vendor mapping for biotech/pharma manufacturing & development
PRODUCT_VENDOR_MAP = {
    # ===== UPSTREAM PROCESS =====
    "Upstream Cell Culture And Fermentation": [
        "Thermo Fisher Scientific",
        "Cytiva",
        "Sartorius",
        "Eppendorf",
        "PBS Biotech",
        "Corning Life Sciences",
        "INFORS HT",
        "Applikon (Getinge)",
        "Kuhner Shaker",
        "Fujifilm Irvine Scientific",
        "Pall (Cytiva)",
        "Merck Millipore",
        "Lonza",
        "Cellexus",
        "HyClone (Cytiva)",
        "Broadley-James",
        "PreSens",
        "ABER Instruments",
        "CerCell",
        "Finesse Solutions",
        "New Brunswick (Eppendorf)",
        "Electrolab Biotech",
    ],
    
    "Upstream Cell Line Development": [
        "Cytiva",
        "Thermo Fisher Scientific",
        "Sartorius",
        "Lonza",
        "Selexis",
        "AGC Biologics",
        "WuXi Biologics",
        "Merck Millipore",
        "Horizon Discovery",
        "ATCC",
    ],
    
    "Upstream Cell Expansion": [
        "Cytiva",
        "Thermo Fisher Scientific",
        "Sartorius",
        "Corning Life Sciences",
        "Eppendorf",
        "PBS Biotech",
        "Lonza",
        "Merck Millipore",
    ],
    
    "Media Optimization": [
        "Sartorius",
        "Cytiva",
        "Thermo Fisher Scientific",
        "Fujifilm Irvine Scientific",
        "Lonza",
        "Merck Millipore",
        "Corning Life Sciences",
        "InVitria",
        "Sheffield Biologics",
    ],
    
    "Bioreactors": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Eppendorf",
        "PBS Biotech",
        "Applikon (Getinge)",
        "INFORS HT",
        "Solaris Biotech",
        "Pierre Guerin",
        "Pall (Cytiva)",
        "New Brunswick (Eppendorf)",
        "Electrolab Biotech",
        "CerCell",
        "Distek",
        "ABEC",
        "Celltainer Biotech",
    ],
    
    # ===== DOWNSTREAM PROCESS =====
    "Downstream Isolation And Purification": [
        "Cytiva",
        "Sartorius",
        "Tosoh Bioscience",
        "Bio-Rad",
        "Thermo Fisher Scientific",
        "Repligen",
        "Purolite Resins",
        "Asahi Kasei Bioprocess",
        "3M Health Care",
        "MilliporeSigma",
        "Pall (Cytiva)",
        "Merck Millipore",
        "Avantor",
        "Novasep",
        "Navigo Proteins",
        "Chromatan",
        "Astrea Bioseparations",
        "Absolute Antibody",
        "ProchromIX",
    ],
    
    "Downstream Polish And Viral Clearance": [
        "Cytiva",
        "Sartorius",
        "Repligen",
        "Asahi Kasei Bioprocess",
        "3M Health Care",
        "Pall (Cytiva)",
        "MilliporeSigma",
        "Purolite Resins",
        "Merck Millipore",
        "Thermo Fisher Scientific",
    ],
    
    "Chromatography": [
        "Cytiva",
        "Sartorius",
        "Bio-Rad",
        "Tosoh Bioscience",
        "Thermo Fisher Scientific",
        "Repligen",
        "Waters",
        "Agilent",
        "MilliporeSigma",
        "Purolite Resins",
        "YMC",
        "Knauer",
        "Sykam",
        "Jasco",
        "Novasep",
        "Kromasil",
        "Sepax Technologies",
        "Phenomenex",
    ],
    
    "Filtration": [
        "Sartorius",
        "Pall (Cytiva)",
        "MilliporeSigma",
        "3M Health Care",
        "Repligen",
        "Asahi Kasei Bioprocess",
        "Thermo Fisher Scientific",
        "Parker Hannifin",
        "Amazon Filters",
        "Eaton",
        "Meissner",
        "Graver Technologies",
        "Porvair Filtration",
        "GVS",
        "Pentair",
    ],
    
    # ===== ANALYTICAL & QC =====
    "Bioprocess Analytical Methods": [
        "Waters",
        "Agilent",
        "SCIEX",
        "Shimadzu",
        "Bruker",
        "Thermo Fisher Scientific",
        "Phenomenex",
        "PerkinElmer",
        "Tecan",
        "Bio-Rad",
        "Sartorius",
        "Beckman Coulter",
        "Molecular Devices",
        "BMG Labtech",
        "Unchained Labs",
        "Wyatt Technology",
        "Malvern Panalytical",
        "Protein Simple",
        "ForteBio (Sartorius)",
        "Genedata",
        "Octet (Sartorius)",
    ],
    
    "Analytical Development": [
        "Waters",
        "Agilent",
        "SCIEX",
        "Shimadzu",
        "Thermo Fisher Scientific",
        "Bruker",
        "PerkinElmer",
        "Bio-Rad",
    ],
    
    "QA/QC": [
        "Waters",
        "Agilent",
        "Bio-Rad",
        "Shimadzu",
        "Thermo Fisher Scientific",
        "Bruker",
        "TSI",
        "Particle Measuring Systems",
        "Sartorius",
        "PerkinElmer",
        "Beckman Coulter",
        "Lighthouse Worldwide Solutions",
        "Climet",
        "Kanomax",
        "BioVigilant (Lighthouse)",
        "RapidMicro Biosystems",
        "Charles River Laboratories",
        "Veltek Associates",
    ],
    
    "Quality Assurance": [
        "Waters",
        "Agilent",
        "Bio-Rad",
        "Thermo Fisher Scientific",
        "Sartorius",
        "TSI",
        "Particle Measuring Systems",
    ],
    
    "Quality Control": [
        "Waters",
        "Agilent",
        "Bio-Rad",
        "Thermo Fisher Scientific",
        "Shimadzu",
        "Bruker",
        "Sartorius",
    ],
    
    # ===== MANUFACTURING & CONTROLS =====
    "Manufacturing": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Lonza",
        "Catalent",
        "Samsung Biologics",
        "WuXi Biologics",
    ],
    
    "GMP Manufacturing": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Lonza",
        "Catalent",
        "Samsung Biologics",
        "WuXi Biologics",
        "AGC Biologics",
    ],
    
    "Clinical Manufacturing": [
        "Lonza",
        "Catalent",
        "Thermo Fisher Scientific (Patheon)",
        "Samsung Biologics",
        "AGC Biologics",
        "WuXi Biologics",
        "Cytiva",
        "Sartorius",
    ],
    
    "Commercial Manufacturing": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "Thermo Fisher Scientific (Patheon)",
        "AGC Biologics",
        "WuXi Biologics",
        "Cytiva",
        "Sartorius",
    ],
    
    "Bioprocess Manufacturing Controls": [
        "Emerson Automation Solutions",
        "Siemens",
        "Rockwell Automation",
        "Honeywell",
        "Blue Mountain",
        "ValGenesis",
        "Werum (Körber)",
        "Emerson DeltaV",
        "Yokogawa",
        "Cytiva",
        "Sartorius",
        "Syncade (Emerson)",
        "Aveva",
        "Dassault Systèmes (BIOVIA)",
        "ICONICS",
        "GE Digital",
        "OSIsoft (AVEVA)",
    ],
    
    "Pharmaceutical Manufacturing Controls": [
        "Emerson Automation Solutions",
        "Siemens",
        "Rockwell Automation",
        "Honeywell",
        "Blue Mountain",
        "ValGenesis",
        "Werum (Körber)",
        "Yokogawa",
        "AZO",
        "Opcenter (Siemens)",
    ],
    
    "Automation": [
        "Emerson Automation Solutions",
        "Siemens",
        "Rockwell Automation",
        "Honeywell",
        "Yokogawa",
        "ABB",
        "Tecan",
        "Hamilton Robotics",
        "Hudson Robotics",
        "HighRes Biosolutions",
        "Brooks Automation",
        "Beckman Coulter",
        "PerkinElmer",
        "Formulatrix",
        "SPT Labtech",
    ],
    
    "MES": [
        "Werum (Körber)",
        "Opcenter (Siemens)",
        "Rockwell Automation",
        "Emerson",
        "Blue Mountain",
        "ValGenesis",
        "Honeywell",
    ],
    
    # ===== SINGLE-USE & MATERIALS =====
    "Single-Use Technologies": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "MilliporeSigma",
        "Pall (Cytiva)",
        "Avantor",
        "Saint-Gobain",
        "Charter Medical",
        "Repligen",
        "Entegris",
        "Meissner",
        "CPC (Colder Products Company)",
        "Sentinel Process Systems",
        "Omega Plastics",
        "Watson-Marlow Fluid Technology Group",
        "Flexbiosys",
        "ThermoGenesis",
    ],
    
    # ===== FACILITY & INFRASTRUCTURE =====
    "Bioprocess Facility Design": [
        "CRB",
        "Jacobs",
        "IPS",
        "DPS Group",
        "CAI",
        "M+W Group (Exyte)",
        "AES Clean Technology",
        "G-Con",
        "Pharmadule Morimatsu",
        "CPDC",
        "Fluor",
        "AECOM",
        "Burns & McDonnell",
        "Stantec",
        "EI Associates",
        "CRB USA",
        "TSNE",
        "HDR",
    ],
    
    "Facility Design": [
        "CRB",
        "Jacobs",
        "IPS",
        "DPS Group",
        "CAI",
        "M+W Group (Exyte)",
        "AES Clean Technology",
        "G-Con",
        "Pharmadule Morimatsu",
        "CPDC",
        "Flad Architects",
    ],
    
    "Contamination Control": [
        "TSI",
        "Particle Measuring Systems",
        "Sartorius",
        "MilliporeSigma",
        "3M Health Care",
        "Ecolab",
        "Veltek Associates",
    ],
    
    "Environmental Monitoring": [
        "TSI",
        "Particle Measuring Systems",
        "Sartorius",
        "Thermo Fisher Scientific",
        "MilliporeSigma",
        "Ecolab",
    ],
    
    # ===== PROCESS DEVELOPMENT =====
    "Process Development": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Lonza",
        "MilliporeSigma",
        "Bio-Rad",
        "Repligen",
    ],
    
    "Process Characterization": [
        "Cytiva",
        "Sartorius",
        "Bio-Rad",
        "Waters",
        "Agilent",
        "Thermo Fisher Scientific",
    ],
    
    "Scale-up": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Lonza",
        "Eppendorf",
        "PBS Biotech",
    ],
    
    "Tech Transfer": [
        "Lonza",
        "Catalent",
        "Samsung Biologics",
        "AGC Biologics",
        "WuXi Biologics",
        "Cytiva",
        "Sartorius",
    ],
    
    "MSAT": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Lonza",
        "MilliporeSigma",
    ],
    
    "Design of Experiments": [
        "Cytiva",
        "Sartorius",
        "Bio-Rad",
        "JMP (SAS)",
        "Minitab",
    ],
    
    # ===== VALIDATION & REGULATORY =====
    "Validation": [
        "ValGenesis",
        "Emerson",
        "Siemens",
        "Sartorius",
        "Cytiva",
        "MasterControl",
    ],
    
    "Process Validation": [
        "ValGenesis",
        "Emerson",
        "Sartorius",
        "Cytiva",
        "MasterControl",
    ],
    
    "CMC": [
        "Catalent",
        "Lonza",
        "Thermo Fisher Scientific (Patheon)",
        "Samsung Biologics",
        "AGC Biologics",
        "WuXi Biologics",
    ],
    
    "Regulatory": [
        "MasterControl",
        "ValGenesis",
        "Veeva Systems",
        "Ennov",
    ],
    
    "Regulatory Submissions": [
        "MasterControl",
        "Veeva Systems",
        "Ennov",
    ],
    
    "Stability": [
        "Thermo Fisher Scientific",
        "Sartorius",
        "Waters",
        "Agilent",
        "MilliporeSigma",
    ],
    
    "Release Testing": [
        "Waters",
        "Agilent",
        "Bio-Rad",
        "Thermo Fisher Scientific",
        "Shimadzu",
    ],
    
    # ===== OUTSOURCING / CDMO =====
    "CMO-CDMO": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "Fujifilm Diosynth Biotechnologies",
        "AGC Biologics",
        "WuXi Biologics",
        "Thermo Fisher Scientific (Patheon)",
        "Bionova",
        "Recipharm",
        "Baxter BioPharma Solutions",
        "CordenPharma",
        "Siegfried",
        "Rentschler Biopharma",
        "Boehringer Ingelheim",
        "Sandoz (Novartis)",
        "Vetter Pharma",
        "Evonik",
        "KBI Biopharma",
        "Emergent BioSolutions",
        "Ajinomoto Bio-Pharma Services",
        "Cobra Biologics",
        "Vigene Biosciences",
        "Oxford Biomedica",
        "Andelyn Biosciences",
        "Alcami",
        "Avid Bioservices",
    ],
    
    "Contract Pharma Manufacturing (OUTPH)": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "Fujifilm Diosynth Biotechnologies",
        "AGC Biologics",
        "WuXi Biologics",
        "Thermo Fisher Scientific (Patheon)",
        "Bionova",
        "Recipharm",
        "Baxter BioPharma Solutions",
        "CordenPharma",
        "Siegfried",
        "Fareva",
    ],
    
    "Outsourcing": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "WuXi Biologics",
        "AGC Biologics",
        "Thermo Fisher Scientific (Patheon)",
    ],
    
    "CDMO Selection": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "WuXi Biologics",
        "AGC Biologics",
        "Fujifilm Diosynth Biotechnologies",
    ],
    
    "Tech Transfer Support": [
        "Lonza",
        "Catalent",
        "Samsung Biologics",
        "AGC Biologics",
        "WuXi Biologics",
        "Cytiva",
        "Sartorius",
    ],
    
    "Comparability Studies": [
        "Lonza",
        "Catalent",
        "Samsung Biologics",
        "Waters",
        "Agilent",
        "Bio-Rad",
    ],
    
    # ===== CELL & GENE THERAPY =====
    "Cell Therapy Manufacturing": [
        "Cytiva",
        "Miltenyi Biotec",
        "Lonza",
        "Thermo Fisher Scientific",
        "Sartorius",
        "MaxCyte",
        "Ori Biotech",
        "G-CON",
        "Catalent Cell & Gene",
        "Lonza Houston",
    ],
    
    # ===== IN-PROCESS & RAW MATERIALS =====
    "In-Process Testing": [
        "Waters",
        "Agilent",
        "Bio-Rad",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Beckman Coulter",
    ],
    
    "Raw Material Qualification": [
        "Sartorius",
        "MilliporeSigma",
        "Thermo Fisher Scientific",
        "Cytiva",
        "Avantor",
    ],
    
    # ===== DISCOVERY & PRECLINICAL =====
    "Target Discovery": [
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Bio-Rad",
        "Agilent",
        "Horizon Discovery",
        "Charles River Laboratories",
    ],
    
    "High-Throughput Screening": [
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Tecan",
        "Hamilton Robotics",
        "Beckman Coulter",
        "Agilent",
    ],
    
    "Lead Optimization": [
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Charles River Laboratories",
        "Evotec",
    ],
    
    "Early Analytical Methods": [
        "Waters",
        "Agilent",
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Shimadzu",
    ],
    
    "Assay Development": [
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Bio-Rad",
        "Sartorius",
        "Beckman Coulter",
    ],
    
    "In Vitro Models": [
        "Thermo Fisher Scientific",
        "Corning Life Sciences",
        "Lonza",
        "Charles River Laboratories",
        "Merck Millipore",
    ],
    
    "In Vivo Models": [
        "Charles River Laboratories",
        "Envigo",
        "Taconic Biosciences",
        "The Jackson Laboratory",
    ],
    
    "Toxicology": [
        "Charles River Laboratories",
        "Envigo",
        "WuXi AppTec",
        "Labcorp Drug Development",
    ],
    
    "Preclinical Assays": [
        "Charles River Laboratories",
        "Thermo Fisher Scientific",
        "PerkinElmer",
        "Bio-Rad",
    ],
    
    "ADME": [
        "Charles River Laboratories",
        "Labcorp Drug Development",
        "WuXi AppTec",
    ],
    
    "PK/PD": [
        "Charles River Laboratories",
        "Labcorp Drug Development",
        "WuXi AppTec",
    ],
    
    # ===== DIGITAL & ADVANCED =====
    "Digital Manufacturing": [
        "Emerson",
        "Siemens",
        "Rockwell Automation",
        "Werum (Körber)",
        "Cytiva",
    ],
    
    "Real-Time Release Testing": [
        "Waters",
        "Agilent",
        "Thermo Fisher Scientific",
        "Sartorius",
    ],
    
    "Continued Process Verification": [
        "Emerson",
        "Sartorius",
        "Cytiva",
        "ValGenesis",
    ],
    
    "Capacity Expansion": [
        "CRB",
        "Jacobs",
        "DPS Group",
        "G-Con",
        "Pharmadule Morimatsu",
    ],
    
    "Process Intensification": [
        "Cytiva",
        "Sartorius",
        "Thermo Fisher Scientific",
        "Repligen",
    ],
    
    # ===== VENDOR EVALUATION (META) =====
    "Vendor Evaluation": [
        "Lonza",
        "Samsung Biologics",
        "Catalent",
        "WuXi Biologics",
        "AGC Biologics",
        "Thermo Fisher Scientific",
        "Cytiva",
        "Sartorius",
    ],
}


def get_potential_vendors_for_topics(topics: List[str]) -> List[str]:
    """
    Given a list of topics/categories, return all unique vendors from
    PRODUCT_VENDOR_MAP that are relevant to ANY of those topics.
    No size-based weighting; include ALL relevant vendors.
    """
    vendors = []
    for t in topics:
        if not t:
            continue
        t_norm = t.strip()
        
        # Direct match (case-sensitive key)
        if t_norm in PRODUCT_VENDOR_MAP:
            vendors.extend(PRODUCT_VENDOR_MAP[t_norm])
            continue
        
        # Fuzzy match (case-insensitive contains)
        for key, vs in PRODUCT_VENDOR_MAP.items():
            if t_norm.lower() in key.lower() or key.lower() in t_norm.lower():
                vendors.extend(vs)
    
    # Return unique list preserving order
    seen = set()
    out = []
    for v in vendors:
        if v not in seen:
            seen.add(v)
            out.append(v)
    
    return out


def get_all_vendors() -> List[str]:
    """
    Return a sorted, de-duplicated list of ALL vendor names across
    PRODUCT_VENDOR_MAP. This will be used to populate the Vendor Fit
    filter in the UI.
    """
    all_vendors = set()
    for vendor_list in PRODUCT_VENDOR_MAP.values():
        all_vendors.update(vendor_list)
    
    return sorted(all_vendors)
