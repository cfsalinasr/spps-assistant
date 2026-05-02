"""Domain models: dataclasses for core SPPS entities."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class ResidueInfo:
    token: str           # e.g. "C(Trt)" or "A"
    base_code: str       # e.g. "C" or "A"
    protection: str      # e.g. "Trt" or ""
    fmoc_mw: float       # g/mol for stoichiometry
    free_mw: float       # g/mol for peptide MW
    stock_conc: float = 0.5          # M, default 0.5 M in DMF
    density_g_ml: Optional[float] = None   # g/mL for liquids; None = solid
    equivalents_multiplier: float = 1.0    # scales the global reactant excess


@dataclass
class Vessel:
    number: int
    name: str
    original_tokens: List[str]
    reversed_tokens: List[str]
    resin_mass_g: float = 0.1
    substitution_mmol_g: float = 0.3

    @property
    def length(self) -> int:
        return len(self.original_tokens)


@dataclass
class SolubilityResult:
    kd_avg: float
    eisenberg_avg: float
    black_mould_avg: float
    is_hydrophobic: bool
    recommendation: str
    light_sensitive: bool
    net_charge_ph7: Optional[float] = None
    pI: Optional[float] = None
    gravy: Optional[float] = None
    orthogonal_groups: List[str] = field(default_factory=list)


@dataclass
class YieldResult:
    vessel_number: int
    vessel_name: str
    peptide_mw: float
    sequence_length: int
    resin_mass_g: float
    substitution_mmol_g: float
    theoretical_yield_mg: float
    formula_shown: str


@dataclass
class CouplingCycle:
    cycle_number: int
    total_cycles: int
    residues_at_position: Dict[str, List[int]]   # token -> list of vessel numbers
    all_vessels: List  # Vessel objects


@dataclass
class SynthesisConfig:
    name: str
    vessel_label: str = 'Vessel'
    vessel_method: str = 'Teabag'
    volume_mode: str = 'stoichiometry'
    activator: str = 'HBTU'
    use_oxyma: bool = True
    base: str = 'DIEA'
    deprotection_reagent: str = 'Piperidine 20%'
    aa_equivalents: float = 3.0
    activator_equivalents: float = 3.0
    base_equivalents: float = 6.0
    include_bb_test: bool = True
    include_kaiser_test: bool = False
    starting_vessel_number: int = 1
    output_directory: str = 'spps_output'
    resin_mass_strategy: str = 'fixed'
    fixed_resin_mass_g: float = 0.1
    target_yield_mg: Optional[float] = None


@dataclass
class MaterialsRow:
    token: str
    protection: str
    fmoc_mw: float
    mmol_needed: float
    mass_mg: float
    stock_conc: float
    volume_ml: float
    notes: str = ''
    formula: str = ''
    volume_ul: Optional[float] = None   # set for liquid reagents; shows instead of mass_mg
