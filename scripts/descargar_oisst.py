"""
Descarga subconjuntos regionales de NOAA OISST v2.1 (diario, 0.25°).

Fuente: repositorio Icechunk público de source.coop (lectura anónima).

Dominio por defecto (bordes de celda): 70°W–85°W, 3°S–18°S, 1991-01-01 a 2025-12-31.

Sobre las coordenadas
---------------------
En OISST v2.1 los valores de `lat` y `lon` son los CENTROS de las celdas de 0.25°
(p. ej. -17.875, -17.625, ..., -3.125). Cada celda abarca ±0.125° alrededor de su
centro. Como los bordes pedidos (-18, -3, 275, 290) caen en bordes de celda,
`slice(-18, -3)` selecciona exactamente las celdas contenidas en el dominio:

    lat: -17.875 ... -3.125   (60 centros)
    lon: -84.875 ... -70.125  (60 centros; 275.125 ... 289.875 en 0–360)

Uso
---
    python scripts/descargar_oisst.py                    # dominio y periodo por defecto
    python scripts/descargar_oisst.py --inicio 2023 --fin 2024 --salida data/prueba.nc
    python scripts/descargar_oisst.py --lat -13 -11 --lon -78 -76 --inicio 2024 --fin 2024 \\
        --salida data/callao_2024.nc                     # otro dominio (bordes, lon en -180..180)

Ejecutar desde la raíz del taller. La descarga se hace año por año en `data/.partes/`
(junto al archivo de salida) y es reanudable: si se interrumpe, al volver a ejecutar solo
baja los años que faltan.

Desde Python (por ejemplo, en el cuaderno), para cualquier dominio y rango de fechas:

    from descargar_oisst import descargar
    ds = descargar("2024-01-01", "2024-03-31", lat=(-13, -11), lon=(-78, -76))
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import xarray as xr

STORE_URL = "https://data.source.coop/ocean-icechunks/noaa-oisst/oisst.icechunk"

# Bordes del dominio por defecto (grados, lon en -180..180)
LAT_DEFECTO = (-18.0, -3.0)
LON_DEFECTO = (-85.0, -70.0)


def conectar_store():
    import icechunk
    import zarr

    zarr.config.set({"async.concurrency": 8})
    repo = icechunk.Repository.open(icechunk.http_storage(STORE_URL))
    auth = icechunk.containers_credentials(
        {p: icechunk.s3_anonymous_credentials() for p in repo.config.virtual_chunk_containers}
    )
    session = repo.reopen(authorize_virtual_chunk_access=auth).readonly_session("main")
    ds = xr.open_zarr(session.store, group="daily", consolidated=False, chunks=None)
    return ds, session.snapshot_id


def _recorte(ds_store, inicio, fin, lat, lon):
    """Lee del store el recorte (time, lat, lon). El store usa lon en 0..360."""
    lon360 = sorted(v % 360 for v in lon)
    sub = ds_store[["sst"]].sel(time=slice(inicio, fin), lat=slice(*sorted(lat)), lon=slice(*lon360))
    return sub.squeeze("zlev", drop=True).load()


def _por_meses(ds_store, inicio, fin, lat, lon, intentos: int = 8):
    """Descarga mes a mes (con reintentos y reconexión) y concatena en el tiempo."""
    inicio, fin = pd.Timestamp(inicio), pd.Timestamp(fin)
    meses = []
    for m0 in pd.date_range(inicio.to_period("M").start_time, fin, freq="MS"):
        m1 = min(m0 + pd.offsets.MonthEnd(0), fin) + pd.Timedelta("1D") - pd.Timedelta("1s")
        for intento in range(1, intentos + 1):
            try:
                meses.append(_recorte(ds_store, max(m0, inicio), m1, lat, lon))
                break
            except Exception:
                if intento == intentos:
                    raise
                time.sleep(min(10 * intento, 60))
                ds_store, _ = conectar_store()
    return xr.concat(meses, dim="time"), ds_store


def descargar_anio(ds_store, anio: int, destino: Path, lat=LAT_DEFECTO, lon=LON_DEFECTO):
    """Descarga un año completo y lo guarda en `destino` (parte reanudable)."""
    serie, ds_store = _por_meses(ds_store, f"{anio}-01-01", f"{anio}-12-31", lat, lon)
    tmp = destino.with_suffix(".tmp")
    serie.to_netcdf(tmp, engine="h5netcdf")
    tmp.replace(destino)
    return ds_store


def _formatear(serie: xr.Dataset, lat, lon, periodo: str, snapshot: str) -> xr.Dataset:
    """Longitudes a -180..180, float32 y metadatos (centros de celda, fuente, dominio)."""
    serie = serie.assign_coords(lon=(((serie["lon"] + 180) % 360) - 180).astype("float32"))
    serie["sst"] = serie["sst"].astype("float32")
    serie["sst"].attrs = {"units": "degC", "long_name": "Daily sea surface temperature"}
    serie["lat"].attrs = {
        "units": "degrees_north", "long_name": "latitude (cell center)",
        "comment": "Centro de celda de 0.25°; la celda abarca lat ± 0.125°.",
    }
    serie["lon"].attrs = {
        "units": "degrees_east", "long_name": "longitude (cell center)",
        "comment": "Centro de celda de 0.25° en convención -180..180; la celda abarca lon ± 0.125°.",
    }
    serie.attrs = {
        "title": "NOAA OISST v2.1 AVHRR-only daily, subconjunto regional",
        "source": "NOAA OISST v2.1 AVHRR-only daily (Huang et al. 2021, J. Climate)",
        "store": STORE_URL,
        "store_snapshot": snapshot,
        "domain_edges": f"lat {lat[0]:g}..{lat[1]:g}, lon {lon[0]:g}..{lon[1]:g} (bordes de celda)",
        "coordinates_are": "cell centers",
        "period": periodo,
        "created_by": "scripts/descargar_oisst.py (taller ReMoHES PUCP 2026)",
    }
    return serie


def _guardar(serie: xr.Dataset, salida: Path) -> None:
    trozos = (min(366, serie.sizes["time"]), serie.sizes["lat"], serie.sizes["lon"])
    enc = {"sst": {"zlib": True, "complevel": 4, "chunksizes": trozos}}
    salida.parent.mkdir(parents=True, exist_ok=True)
    tmp = salida.with_suffix(".tmp.nc")
    serie.to_netcdf(tmp, engine="netcdf4" if _hay_netcdf4() else "h5netcdf", encoding=enc)
    tmp.replace(salida)


def descargar(inicio: str, fin: str, lat=LAT_DEFECTO, lon=LON_DEFECTO,
              salida: str | Path | None = None) -> xr.Dataset:
    """Descarga OISST v2.1 diario para un dominio y un rango de fechas cualesquiera.

    `lat` y `lon` son los bordes del dominio en grados (lon en -180..180, oeste negativo).
    Con bordes múltiplos de 0.25 se obtienen exactamente las celdas contenidas en el dominio.
    Si se da `salida`, guarda además un NetCDF. Pensado para recortes cortos: para series
    largas conviene la línea de comandos, que descarga año por año y se puede reanudar.
    """
    lat, lon = tuple(sorted(lat)), tuple(sorted(lon))
    ds_store, snapshot = conectar_store()
    serie, _ = _por_meses(ds_store, inicio, fin, lat, lon)
    serie = _formatear(serie, lat, lon, f"{inicio} a {fin}", snapshot)
    if salida is not None:
        _guardar(serie, Path(salida))
    return serie


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inicio", type=int, default=1991, help="primer año (incl.)")
    ap.add_argument("--fin", type=int, default=2025, help="último año (incl.)")
    ap.add_argument("--lat", type=float, nargs=2, default=LAT_DEFECTO, metavar=("SUR", "NORTE"),
                    help="bordes de latitud (por defecto -18 -3)")
    ap.add_argument("--lon", type=float, nargs=2, default=LON_DEFECTO, metavar=("OESTE", "ESTE"),
                    help="bordes de longitud en -180..180 (por defecto -85 -70)")
    ap.add_argument("--salida", type=Path, default=Path("data/oisst_peru_1991_2025.nc"))
    args = ap.parse_args()
    lat, lon = tuple(sorted(args.lat)), tuple(sorted(args.lon))

    # Las partes anuales se guardan por dominio, para no mezclar recortes distintos
    etiqueta = "" if (lat, lon) == (LAT_DEFECTO, LON_DEFECTO) else f"_{lat[0]:g}_{lat[1]:g}_{lon[0]:g}_{lon[1]:g}"
    partes_dir = args.salida.parent / f".partes{etiqueta}"
    partes_dir.mkdir(parents=True, exist_ok=True)

    print("Conectando al repositorio Icechunk de NOAA OISST v2.1...", flush=True)
    ds_store, snapshot = conectar_store()
    print(f"  snapshot: {snapshot}", flush=True)

    partes = []
    for anio in range(args.inicio, args.fin + 1):
        parte = partes_dir / f"{anio}.nc"
        partes.append(parte)
        if parte.exists():
            continue
        t0 = time.time()
        ds_store = descargar_anio(ds_store, anio, parte, lat, lon)
        print(f"  {anio} descargado en {time.time() - t0:.1f} s", flush=True)

    print("Consolidando...", flush=True)
    serie = xr.concat([xr.open_dataset(p, engine="h5netcdf").load() for p in partes], dim="time")
    serie = _formatear(serie, lat, lon, f"{args.inicio}-01-01 a {args.fin}-12-31", snapshot)
    _guardar(serie, args.salida)
    print(f"Guardado: {args.salida}  dims={dict(serie.sizes)}", flush=True)


def _hay_netcdf4() -> bool:
    try:
        import netCDF4  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
