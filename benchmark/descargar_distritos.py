"""Descarga (o reutiliza) las redes viales de los distritos indicados.

Uso:  python -m benchmark.descargar_distritos miraflores san-isidro santiago-de-surco
      python -m benchmark.descargar_distritos --forzar miraflores   (actualización manual)
"""

from __future__ import annotations

import argparse
import logging

from backend.configuracion.ajustes import obtener_ajustes
from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.gestor_grafos import GestorGrafos


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga redes viales OSM por distrito")
    parser.add_argument("distritos", nargs="*", help="identificadores (vacío = listar catálogo)")
    parser.add_argument("--forzar", action="store_true", help="volver a descargar aunque exista")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ajustes = obtener_ajustes()
    catalogo = CatalogoDistritos(ajustes)
    gestor = GestorGrafos(ajustes, catalogo)
    if not args.distritos:
        for d in catalogo.listar():
            marca = "✔" if gestor.esta_descargado(d.id_distrito) else " "
            print(f"[{marca}] {d.id_distrito:28s} {d.provincia:20s} {d.area_km2:7.2f} km²  elegible={d.elegible}")
        return
    for id_distrito in args.distritos:
        distrito = catalogo.obtener(id_distrito)
        if distrito is None:
            print(f"Distrito desconocido: {id_distrito}")
            continue
        meta = gestor.descargar_y_guardar(distrito, forzar=args.forzar)
        print(f"{id_distrito}: {meta['nodos']} nodos, {meta['aristas']} aristas (fuente: {meta['fuente']})")


if __name__ == "__main__":
    main()
