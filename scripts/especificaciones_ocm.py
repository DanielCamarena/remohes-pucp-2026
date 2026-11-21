# Copyright 2026 Daniel Camarena
# SPDX-License-Identifier: Apache-2.0
"""
Especificaciones de xhw para detectar Olas de Calor Marinas (OCM) en una malla OISST.

xhw no trae perfiles predefinidos: cada análisis declara sus cuatro contratos completos
(SourceRef, GridSpec, DefinitionSpec, BaselineSpec), para que toda decisión quede registrada.
Los ejemplos de xhw y de xhw-benchmark agrupan esos contratos en funciones auxiliares
(`surface_grid`, `marine_definition`, `fixed_baseline` en examples/_data.py); este módulo
hace lo mismo para el taller. Solo quedan como argumentos los parámetros que un usuario
cambiaría; el resto es fijo para OCM con OISST.

Uso:
    from especificaciones_ocm import especificaciones_ocm
    source, grid, definition, baseline = especificaciones_ocm()
"""

from __future__ import annotations

from datetime import datetime, timezone

import xhw


def especificaciones_ocm(
    periodo_referencia: tuple[str, str] = ("1991-01-01", "2020-12-31"),
    percentil: float = 90.0,
    duracion_min: int = 5,
    brecha_max: int = 2,
    ventana_dias: int = 11,
    suavizado_dias: int = 31,
    dataset_id: str = "noaa_oisst_v2.1_peru",
):
    """Devuelve (source, grid, definition, baseline) según Hobday et al. (2016, 2018).

    Los valores por defecto son los de Hobday et al. (2016): P90 sobre 1991-2020 con
    ventana de 11 días y suavizado circular de 31 días, eventos de al menos 5 días que se
    unen si la brecha es de 2 días o menos, y categorías de Hobday et al. (2018).
    """
    # 1. Procedencia del dato
    source = xhw.SourceRef(
        dataset_id=dataset_id, variable="sst", product_status="final",
        accessed=datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # 2. Malla: superficie regular (time, lat, lon) a 0.25°, solo celdas oceánicas
    grid = xhw.GridSpec(
        support="surface", topology="structured", time_dim="time", spatial_dims=("lat", "lon"),
        coords=xhw.CoordRoles(lat="lat", lon="lon"), calendar="standard", frequency="1D",
        time_axes="single", periodic_x=False, cell_measure=xhw.CellMeasure(kind="unit"),
        vertical=None, domain="ocean", domain_mask="domain_mask", domain_fraction=None,
        native=xhw.NativeGrid(product="oisst", resolution="0.25deg", is_native=True))

    # 3. Definición del evento: SST > P90 durante >= 5 días, uniendo brechas <= 2 días
    definition = xhw.DefinitionSpec(
        profile="hobday2016", phenomenon="mhw", variable="sea_surface_temperature",
        combination="single", daily_statistic="native", day_definition="native",
        tail="upper", comparator=">", threshold_kind="percentile", percentile=percentil,
        absolute_threshold=None, min_duration_days=duracion_min, max_gap_days=brecha_max,
        join_rule="qualify_then_join", missing_policy="as_non_exceedance",
        season_months=None, category_scheme="hobday2018")

    # 4. Línea base: climatología fija, percentil tipo 7, 29-feb interpolado (eje de 366 días).
    #    min_samples exige el 80 % de las muestras posibles (264 de 11 x 30 en 1991-2020).
    anios = int(periodo_referencia[1][:4]) - int(periodo_referencia[0][:4]) + 1
    baseline = xhw.BaselineSpec(
        method="fixed_climatology", computed_on="temperature",
        reference_period=periodo_referencia, source=source,
        doy_window_days=ventana_dias, smoothing_window_days=suavizado_dias,
        percentile_estimator="hyndman_fan_7", leap_day_policy="hobday_366_interp",
        min_samples=round(0.8 * ventana_dias * anios), fit_mode="retrospective",
        available_until=None)

    return source, grid, definition, baseline
