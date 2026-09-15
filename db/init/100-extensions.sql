-- Piege : ce script ne rejoue qu'a la premiere initialisation, quand PGDATA est vide.
-- Le modifier ensuite reste sans effet tant que le volume n'est pas detruit.

CREATE EXTENSION IF NOT EXISTS timescaledb;
