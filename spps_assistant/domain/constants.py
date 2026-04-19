"""Domain constants: MW tables, hydrophobicity scales, valid codes."""

# Free amino acid RESIDUE MWs (for peptide MW = sum residue MWs + 18.0152)
FREE_RESIDUE_MW = {
    'A': 71.08,  'R': 156.19, 'N': 114.10, 'D': 115.09, 'C': 103.14,
    'Q': 128.13, 'E': 129.12, 'G': 57.05,  'H': 137.14, 'I': 113.16,
    'L': 113.16, 'K': 128.17, 'M': 131.20, 'F': 147.18, 'P': 97.12,
    'S': 87.08,  'T': 101.10, 'W': 186.21, 'Y': 163.18, 'V': 99.13,
    # Non-proteinogenic
    'B': 85.08,   # Aib
    'U': 150.05,  # Sec
    'O': 237.30,  # Pyl
    'X': 111.10,  # unknown (average)
}

# Fmoc-protected MW for standard AAs (commonly used protection schemes)
FMOC_MW_DEFAULTS = {
    'A':        311.3,
    'G':        297.3,
    'V':        339.4,
    'L':        353.4,
    'I':        353.4,
    'P':        337.4,
    'F':        387.4,
    'W(Boc)':   526.6,
    'W':        525.6,   # Fmoc-Trp-OH (without Boc)
    'M':        371.4,
    'S(tBu)':   383.4,
    'S':        305.3,
    'T(tBu)':   397.5,
    'T':        319.3,
    'C(Trt)':   585.7,
    'C(Acm)':   446.5,
    'C':        343.4,
    'Y(tBu)':   459.5,
    'Y':        381.4,
    'H(Trt)':   619.7,
    'H':        387.4,
    'K(Boc)':   468.6,
    'K':        368.4,
    'R(Pbf)':   648.8,
    'R':        474.5,
    'D(OtBu)':  411.5,
    'D':        311.3,   # needs sidechain protection
    'E(OtBu)':  425.5,
    'E':        325.3,
    'N(Trt)':   596.7,
    'N':        352.3,
    'Q(Trt)':   610.7,
    'Q':        366.4,
    # Non-standard
    'B':        285.3,
    'U':        382.3,
    'O':        459.5,
    'X':        353.4,
}

VALID_BASE_CODES = set('ACDEFGHIKLMNPQRSTVWYBOUX')

# Kyte-Doolittle scale
KD_SCALE = {
    'A':  1.8,  'R': -4.5, 'N': -3.5, 'D': -3.5, 'C':  2.5, 'Q': -3.5,
    'E': -3.5,  'G': -0.4, 'H': -3.2, 'I':  4.5,  'L':  3.8, 'K': -3.9,
    'M':  1.9,  'F':  2.8, 'P': -1.6, 'S': -0.8,  'T': -0.7, 'W': -0.9,
    'Y': -1.3,  'V':  4.2,
}

# Eisenberg consensus scale
EISENBERG_SCALE = {
    'A':  0.25, 'R': -1.76, 'N': -0.64, 'D': -0.72, 'C':  0.04, 'Q': -0.69,
    'E': -0.62, 'G':  0.16, 'H': -0.40, 'I':  0.73,  'L':  0.53, 'K': -1.10,
    'M':  0.26, 'F':  0.61, 'P': -0.07, 'S': -0.26,  'T': -0.18, 'W':  0.37,
    'Y':  0.02, 'V':  0.54,
}

# Black & Mould normalized scale (0-1, >0.5 = hydrophobic)
BLACK_MOULD_SCALE = {
    'A': 0.616, 'R': 0.000, 'N': 0.236, 'D': 0.028, 'C': 0.680, 'Q': 0.251,
    'E': 0.043, 'G': 0.501, 'H': 0.165, 'I': 0.943, 'L': 0.943, 'K': 0.283,
    'M': 0.738, 'F': 1.000, 'P': 0.711, 'S': 0.359, 'T': 0.450, 'W': 0.878,
    'Y': 0.880, 'V': 0.825,
}

# pKa values for net charge / pI calculation
PKA_VALUES = {
    'N_term': 8.0,  'C_term': 3.1,
    'D': 3.9,  'E': 4.1,  'H': 6.5,  'C': 8.3,  'Y': 10.1,  'K': 10.5,  'R': 12.5,
}

ACTIVATORS = ['HBTU', 'TBTU', 'HCTU', 'DIC', 'DCC']
BASES = ['DIEA', 'Pyridine', 'None']
DEPROTECTION_REAGENTS = ['Piperidine 20%', 'Piperazine 20%']
VESSEL_LABELS = ['Vessel', 'Bag', 'Syringe', 'Column']
VESSEL_METHODS = ['Teabag', 'Syringe/Reactor']
VOLUME_MODES = ['stoichiometry', 'legacy']
RESIN_MASS_STRATEGIES = ['fixed', 'target_highest', 'target_average']

# Three-letter code mapping for display
THREE_LETTER_CODE = {
    'A': 'Ala', 'C': 'Cys', 'D': 'Asp', 'E': 'Glu', 'F': 'Phe',
    'G': 'Gly', 'H': 'His', 'I': 'Ile', 'K': 'Lys', 'L': 'Leu',
    'M': 'Met', 'N': 'Asn', 'P': 'Pro', 'Q': 'Gln', 'R': 'Arg',
    'S': 'Ser', 'T': 'Thr', 'V': 'Val', 'W': 'Trp', 'Y': 'Tyr',
    'B': 'Aib', 'U': 'Sec', 'O': 'Pyl', 'X': 'Xaa',
}
