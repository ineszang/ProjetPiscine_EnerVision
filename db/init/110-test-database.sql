-- Contrainte : le nom de cette base est code en dur dans apps/backend/tests/conftest.py.
-- Elle sert la suite de tests de la stack locale, pas un deploiement.

CREATE DATABASE enervision_test;

\connect enervision_test

CREATE EXTENSION IF NOT EXISTS timescaledb;
