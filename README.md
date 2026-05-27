# Urban Service Equity Intelligence Platform

A portfolio analytics engineering project comparing urban service-request patterns between NYC 311 and Barcelona IRIS.

## Project goal

Build a reproducible analytics platform that ingests city service-request data, stores raw data in Postgres, transforms it with dbt, and exposes comparable service equity metrics through Superset dashboards.

## Core stack

- Python ingestion
- Postgres
- dbt
- Apache Superset
- Docker Compose
- Anaconda
- VS Code
- Git / GitHub

## Initial scope

Version 1 focuses on descriptive analytics and BI, not forecasting or machine learning.

The main analytical objective is to standardize NYC and Barcelona service-request data into a canonical model that supports comparison across city, area, service category, request status, backlog, resolution time, SLA breach proxy, and request density.

## Planned architecture

Python ingestion -> Postgres raw schemas -> dbt staging models -> dbt canonical/intermediate models -> dbt marts -> Superset dashboards -> GitHub portfolio documentation

## Target portfolio roles

- Analytics Engineer
- BI Analyst
- Data Analyst
- Analytics Consultant

## Status

Project initialized.
