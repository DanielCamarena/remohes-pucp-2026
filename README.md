# Taller ReMoHES PUCP 2026: Detección y Análisis de Olas de Calor Marinas

Material del taller sobre **Olas de Calor Marinas (OCM)** en la costa peruana: cuaderno, datos satelitales NOAA OISST v2.1 (1991–2025) y esquemas conceptuales. Sigue la metodología de **Hobday et al. (2016, 2018)** y usa la librería [`xhw`](https://github.com/DanielCamarena/xhw).

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DanielCamarena/remohes-pucp-2026/blob/main/remohes-pucp-2026-taller-colab.ipynb)

![Afiche del seminario-taller ReMoHES](assets/Afiche%20seminario-taller%20ReMoHES.png)

---

## 🧠 Contenido

1. **Configuración del entorno.**
2. **Marco metodológico:** definición de una OCM, reglas de duración y brecha, categorías I–IV, y cálculo de la climatología y el umbral P90.
3. **Datos NOAA OISST v2.1:** producto, dominio (70°W–85°W, 3°S–18°S), centros de píxel y descarga en tiempo real del año en curso.
4. **Detección con `xhw`:** los cuatro contratos de `xhw`, climatología, detección y catálogo de eventos para las 1805 celdas oceánicas, y análisis exploratorio en Chimbote.
5. **Análisis espacial y temporal:** Paita, Chimbote e Ilo durante El Niño Costero 2017 y El Niño 2023–2024; mapas de días, intensidad, categoría e intensidad acumulada.
6. **Comparación con `marineHeatWaves` (E. Oliver):** mismos eventos, diferencias de milésimas de grado y tiempo de cómputo.
7. **Resumen y perspectivas:** líneas base que siguen el calentamiento (STL, Bonino et al., 2023).

`remohes-pucp-2026-taller.ipynb` se puede leer directamente en GitHub, con todas sus figuras y tablas ya calculadas.

---

## 🚀 Cómo usarlo

### Google Colab
Abre el cuaderno con el botón **Open in Colab**. La primera celda clona este repositorio (datos incluidos) e instala solo los paquetes que Colab no trae (`requirements-colab.txt`).

### En tu computadora
```bash
git clone https://github.com/DanielCamarena/remohes-pucp-2026.git
cd remohes-pucp-2026
python -m venv remohes-env                 # o: conda create -p ./remohes-env python=3.13
remohes-env\Scripts\activate               # Linux/macOS: source remohes-env/bin/activate
pip install -r requirements.txt
jupyter lab remohes-pucp-2026-taller.ipynb
```
Ejecuta el cuaderno desde la raíz del repositorio: las rutas `data/`, `assets/`, `scripts/` y `vendor/` son relativas.

---

## 📁 Estructura

```text
remohes-pucp-2026/
├── remohes-pucp-2026-taller.ipynb        # Cuaderno del taller, con todas las salidas
├── remohes-pucp-2026-taller-colab.ipynb  # Versión para Colab (sin salidas)
├── requirements.txt                      # Entorno local completo (versiones de Colab)
├── requirements-colab.txt                # Solo lo que Colab no trae
├── data/
│   └── oisst_peru_1991_2025.nc           # NOAA OISST v2.1 diario, costa de Perú (≈40 MB)
├── scripts/
│   ├── descargar_oisst.py                # Descarga OISST (dominio y periodo configurables)
│   └── especificaciones_ocm.py           # Los 4 contratos de xhw para OCM (Hobday 2016, 2018)
├── vendor/
│   ├── marineHeatWaves.py                # Librería de E. Oliver, parcheada para numpy >= 2
│   └── LICENSE-marineHeatWaves.txt       # GPL-3.0-or-later
├── assets/                               # Esquemas (PNG) y afiche
└── docs/
    ├── TallerReMoHES_AP.pdf              # Diapositivas del taller (parte 1 de 4)
    └── referencias.md                    # Artículos citados, con DOI
```

---

## 🧪 Entorno de referencia

El cuaderno se validó con las versiones de **Google Colab** (noviembre de 2026):

| Paquete | Versión |
| :--- | :--- |
| Python | 3.13 |
| numpy / pandas / xarray | 2.4.6 / 2.2.3 / 2025.12.0 |
| matplotlib / scipy | 3.10.0 / 1.16.3 |
| h5netcdf / h5py | 1.8.3 / 3.16.0 |
| zarr / icechunk | 3.4.2 / 2.3.1 (solo para descargar datos) |
| xhw | 0.0.1, commit `aa44a80` de [DanielCamarena/xhw](https://github.com/DanielCamarena/xhw) |

`requirements-colab.txt` tiene solo lo que Colab no trae; `requirements.txt` fija además las versiones preinstaladas en Colab. `marineHeatWaves` no se instala con pip: la versión publicada falla con numpy ≥ 2, así que se usa la copia de `vendor/`, con los cambios documentados en su encabezado.

---

## 🛰️ Datos

`data/oisst_peru_1991_2025.nc` es un subconjunto de **NOAA OISST v2.1 AVHRR-only** (diario, 0,25°; Huang et al., 2021), descargado del repositorio público Icechunk de [source.coop](https://source.coop).

| | Bordes del dominio | Centros de píxel (`lat`, `lon`) |
| :--- | :--- | :--- |
| Latitud | 18°S – 3°S | −17.875 … −3.125 (60) |
| Longitud | 85°W – 70°W | −84.875 … −70.125 (60) |
| Tiempo | 1991-01-01 – 2025-12-31 | diario (12 784 días) |

Las coordenadas son **centros de celda**: cada valor representa la celda de ±0,125° alrededor de su centro.

Para regenerar el archivo (≈30–40 min, reanudable) o descargar otro dominio o periodo:
```bash
python scripts/descargar_oisst.py
python scripts/descargar_oisst.py --lat -13 -11 --lon -78 -76 --inicio 2024 --fin 2024 --salida data/callao_2024.nc
```
Desde Python: `descargar("2026-01-01", "2026-11-20", lat=(-18, -3), lon=(-85, -70))`. El cuaderno lo usa para bajar el año en curso en tiempo real (sección 3.1); esos datos no se guardan en el repositorio.

---

## ⚖️ Licencias de terceros

- `vendor/marineHeatWaves.py`: copia modificada de marineHeatWaves (E. C. J. Oliver), GPL-3.0-or-later; ver `vendor/LICENSE-marineHeatWaves.txt` y su encabezado.
- Datos NOAA OISST v2.1: dominio público (NOAA NCEI).

## 📚 Referencias

Ver [docs/referencias.md](docs/referencias.md): Hobday et al. (2016, 2018), Hyndman y Fan (1996), Huang et al. (2021) y Bonino et al. (2023).
