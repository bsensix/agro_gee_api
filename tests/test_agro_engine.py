import pytest
import math
import agro_gee_api.services.agro_engine as agro_engine

from agro_gee_api.services.agro_engine import (
    gdd_day,
    phase_by_cycle,
    resolve_hybrid_phase,
)


def test_gdd_day_when_tmean_above_tcap_clamps_to_tcap() -> None:
    assert gdd_day(tmean_c=35.0, tbase_c=10.0, tcap_c=30.0) == 20.0


def test_phase_by_cycle_at_10pct_boundary_uses_next_half_open_interval() -> None:
    assert phase_by_cycle(crop="soybean", pct_cycle=10.0).macro == "vegetative"


def test_phase_by_cycle_at_100pct_maps_to_maturation() -> None:
    assert phase_by_cycle(crop="soybean", pct_cycle=100.0).macro == "maturation"


def test_phase_by_cycle_above_100pct_raises_value_error() -> None:
    with pytest.raises(ValueError, match="pct_cycle out of range"):
        phase_by_cycle(crop="soybean", pct_cycle=100.0001)


def test_phase_by_cycle_below_0pct_raises_value_error() -> None:
    with pytest.raises(ValueError, match="pct_cycle out of range"):
        phase_by_cycle(crop="soybean", pct_cycle=-0.0001)


def test_resolve_hybrid_phase_lower_order_means_more_delayed() -> None:
    by_cycle_order = 3
    by_gdd_order = 2

    most_delayed_order = resolve_hybrid_phase(
        by_cycle_order=by_cycle_order,
        by_gdd_order=by_gdd_order,
    )

    assert most_delayed_order == 2


def test_resolve_hybrid_phase_equal_orders_returns_that_order() -> None:
    assert resolve_hybrid_phase(by_cycle_order=2, by_gdd_order=2) == 2


def test_resolve_hybrid_phase_by_cycle_lower_than_by_gdd_returns_by_cycle() -> None:
    assert resolve_hybrid_phase(by_cycle_order=1, by_gdd_order=3) == 1


def test_kelvin_to_celsius_conversion() -> None:
    assert agro_engine.kelvin_to_celsius(300.0) == pytest.approx(26.85, abs=1e-2)


def test_meters_to_mm_conversion() -> None:
    assert agro_engine.meters_to_mm(0.012) == pytest.approx(12.0)


def test_ra_extraterrestrial_radiation_mm_eq_matches_reference_value() -> None:
    ra_mm_eq = agro_engine.extraterrestrial_radiation_mm_eq(
        day_of_year=172,
        latitude_deg=-15.0,
    )
    assert ra_mm_eq == pytest.approx(10.8438, abs=1e-3)


def test_etc_day_is_et0_times_kc() -> None:
    assert agro_engine.etc_day(et0_mm_day=4.2, kc=1.1) == pytest.approx(4.62)


def test_et0_hargreaves_uses_fao56_ra_units() -> None:
    tmin_c = 20.0
    tmax_c = 30.0
    tmean_c = 25.0
    ra_mm_eq = agro_engine.extraterrestrial_radiation_mm_eq(
        day_of_year=172,
        latitude_deg=-15.0,
    )

    et0 = agro_engine.et0_hargreaves_mm_day(
        tmin_c=tmin_c,
        tmax_c=tmax_c,
        tmean_c=tmean_c,
        ra_mm_eq=ra_mm_eq,
    )

    expected = (
        0.0023 * (tmean_c + 17.8) * math.sqrt(tmax_c - tmin_c) * (ra_mm_eq * 2.45)
    )
    assert et0 == pytest.approx(expected)


@pytest.mark.parametrize(
    ("soil_mm", "p_mm", "etc_mm", "taw_mm", "expected"),
    [
        (60.0, 30.0, 10.0, 100.0, (80.0, 0.0, 0.0)),
        (95.0, 20.0, 5.0, 100.0, (100.0, 10.0, 0.0)),
        (15.0, 0.0, 25.0, 100.0, (0.0, 0.0, 10.0)),
    ],
)
def test_bucket_step_tracks_soil_excess_and_deficit(
    soil_mm: float,
    p_mm: float,
    etc_mm: float,
    taw_mm: float,
    expected: tuple[float, float, float],
) -> None:
    assert (
        agro_engine.bucket_step(
            soil_mm=soil_mm,
            p_mm=p_mm,
            etc_mm=etc_mm,
            taw_mm=taw_mm,
        )
        == expected
    )


def test_water_deficit_score_uses_weighted_frequency_and_intensity() -> None:
    assert agro_engine.water_deficit_score(
        deficit_freq=0.50, deficit_intensity=0.25
    ) == pytest.approx(0.40)


def test_water_excess_score_uses_weighted_frequency_and_intensity() -> None:
    assert agro_engine.water_excess_score(
        excess_freq=0.50, excess_intensity=0.25
    ) == pytest.approx(0.40)


@pytest.mark.parametrize(
    ("deficit_freq", "deficit_intensity", "excess_freq", "excess_intensity"),
    [
        (-1.0, -2.0, -3.0, -4.0),
        (2.0, 3.0, 4.0, 5.0),
    ],
)
def test_water_score_helpers_clamp_outputs_in_zero_to_one_range(
    deficit_freq: float,
    deficit_intensity: float,
    excess_freq: float,
    excess_intensity: float,
) -> None:
    deficit_score = agro_engine.water_deficit_score(
        deficit_freq=deficit_freq,
        deficit_intensity=deficit_intensity,
    )
    excess_score = agro_engine.water_excess_score(
        excess_freq=excess_freq,
        excess_intensity=excess_intensity,
    )

    assert 0.0 <= deficit_score <= 1.0
    assert 0.0 <= excess_score <= 1.0


def test_classify_water_status_deficit_branch() -> None:
    assert (
        agro_engine.classify_water_status(deficit_score=0.45, excess_score=0.44)
        == "deficit"
    )


def test_classify_water_status_excesso_branch() -> None:
    assert (
        agro_engine.classify_water_status(deficit_score=0.30, excess_score=0.45)
        == "excesso"
    )


def test_classify_water_status_adequado_when_scores_below_threshold() -> None:
    assert (
        agro_engine.classify_water_status(deficit_score=0.44, excess_score=0.43)
        == "adequado"
    )


def test_classify_water_status_tie_at_or_above_threshold_prefers_deficit() -> None:
    assert (
        agro_engine.classify_water_status(deficit_score=0.45, excess_score=0.45)
        == "deficit"
    )


def test_thermal_score_adds_persistence_bonus_at_3_days() -> None:
    assert agro_engine.thermal_score(
        base_score=0.40, persistence_days=3
    ) == pytest.approx(0.55)


def test_thermal_score_below_3_days_does_not_include_3_day_bonus() -> None:
    assert agro_engine.thermal_score(
        base_score=0.40, persistence_days=2
    ) == pytest.approx(0.40)


def test_thermal_score_adds_persistence_bonus_at_5_days() -> None:
    assert agro_engine.thermal_score(
        base_score=0.40, persistence_days=5
    ) == pytest.approx(0.70)


def test_thermal_score_below_5_days_does_not_include_5_day_bonus() -> None:
    assert agro_engine.thermal_score(
        base_score=0.40, persistence_days=4
    ) == pytest.approx(0.55)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.32, "baixo"),
        (0.33, "medio"),
        (0.66, "medio"),
        (0.67, "alto"),
    ],
)
def test_risk_class_boundary_values(score: float, expected: str) -> None:
    assert agro_engine.risk_class(score=score) == expected
