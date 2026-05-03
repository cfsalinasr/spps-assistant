"""Volume and mass calculations for SPPS stoichiometry."""


def calc_volume_stoichiometry(
    n_vessels: int,
    equivalents: float,
    resin_mmol: float,
    stock_conc_m: float,
) -> float:
    """Calculate reagent volume using stoichiometric mode.

    Formula: Volume (mL) = (n_vessels * equivalents * resin_mmol) / stock_conc_m

    Args:
        n_vessels: Number of vessels requiring this reagent
        equivalents: Molar equivalents relative to resin loading
        resin_mmol: mmol of resin per vessel (resin_mass_g * substitution_mmol_g)
        stock_conc_m: Stock solution concentration in Molar

    Returns:
        Volume in mL
    """
    if stock_conc_m <= 0:
        raise ValueError(f"Stock concentration must be positive, got {stock_conc_m}")
    return (n_vessels * equivalents * resin_mmol) / stock_conc_m


def calc_volume_legacy(n_vessels: int) -> float:
    """Legacy mode: 2 mL per vessel (from original Spys.pl).

    Args:
        n_vessels: Number of vessels requiring this reagent

    Returns:
        Volume in mL (2 mL × n_vessels)
    """
    return n_vessels * 2.0


def calc_activator_volume(
    n_vessels: int,
    equivalents: float,
    resin_mmol: float,
    stock_conc_m: float,
) -> float:
    """Calculate activator volume (stoichiometric mode).

    Args:
        n_vessels: Number of vessels using this activator
        equivalents: Activator equivalents relative to resin loading
        resin_mmol: mmol of resin per vessel
        stock_conc_m: Activator stock concentration in Molar

    Returns:
        Volume in mL
    """
    return calc_volume_stoichiometry(n_vessels, equivalents, resin_mmol, stock_conc_m)


def calc_base_volume(
    n_vessels: int,
    equivalents: float,
    resin_mmol: float,
    stock_conc_m: float,
) -> float:
    """Calculate base (e.g. DIEA) volume (stoichiometric mode).

    Args:
        n_vessels: Number of vessels using this base
        equivalents: Base equivalents relative to resin loading
        resin_mmol: mmol of resin per vessel
        stock_conc_m: Base stock concentration in Molar

    Returns:
        Volume in mL
    """
    return calc_volume_stoichiometry(n_vessels, equivalents, resin_mmol, stock_conc_m)


def calc_mass_mg(mmol: float, fmoc_mw: float) -> float:
    """Calculate mass of Fmoc-AA to weigh out.

    Formula: mass_mg = mmol * fmoc_mw   (since 1 mmol × g/mol = mg)

    Args:
        mmol: Millimoles needed
        fmoc_mw: Molecular weight of Fmoc-protected amino acid (g/mol)

    Returns:
        Mass in milligrams
    """
    return mmol * fmoc_mw


def derive_equivalents(aa_eq: float) -> tuple:
    """Derive activator and base equivalents from the global reactant excess.

    Per-reagent multipliers in the materials file scale individual reagents;
    the returned values are the common base equivalents for SynthesisConfig.

    Args:
        aa_eq: Global reactant excess (must be > 0)

    Returns:
        Tuple of (activator_equivalents, base_equivalents), both equal to aa_eq
    """
    return aa_eq, aa_eq


def format_volume_formula(
    n_vessels: int,
    equivalents: float,
    resin_mmol: float,
    stock_conc_m: float,
    volume_ml: float,
) -> str:
    """Format a GMP-compliant volume calculation formula string.

    Args:
        n_vessels: Number of vessels
        equivalents: Equivalents used
        resin_mmol: mmol per vessel
        stock_conc_m: Stock concentration in M
        volume_ml: Computed volume in mL

    Returns:
        Human-readable formula string
    """
    return (
        f"V = ({n_vessels} vessels × {equivalents} eq × {resin_mmol:.4f} mmol) "
        f"/ {stock_conc_m} M = {volume_ml:.3f} mL"
    )
