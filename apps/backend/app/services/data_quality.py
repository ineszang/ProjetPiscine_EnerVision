# Contrainte : `ck_reading_quality` accepte NULL et quatre valeurs seulement, alors que le contrat
# frontend n'a aucune valeur pour l'absence de qualité. `qualite_ou_critique()` replie donc sur
# `critical`, la seule des quatre qui n'induise pas une confiance qu'on n'a pas. `QUALITES_CONNUES`
# reste exposé pour les appelants qui doivent distinguer un `critical` stocké d'un repli.

from typing import Literal, get_args

DataQuality = Literal["good", "partial", "degraded", "critical"]

QUALITES_CONNUES: frozenset[str] = frozenset(get_args(DataQuality))

_PAR_VALEUR: dict[str, DataQuality] = {valeur: valeur for valeur in get_args(DataQuality)}


def qualite_ou_critique(valeur: str | None) -> DataQuality:
    if valeur is None:
        return "critical"
    return _PAR_VALEUR.get(valeur, "critical")
