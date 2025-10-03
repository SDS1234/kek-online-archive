## archive of [kek-online.de](https://www.kek-online.de/medienkonzentration/mediendatenbank#/)

[![Scraper](https://github.com/defgsus/kek-online-archive/actions/workflows/clock.yml/badge.svg)](https://github.com/defgsus/kek-online-archive/actions/workflows/clock.yml)

The *Kommission zur Ermittlung der Konzentration 
im Medienbereich* (KEK), collects and publishes shareholding
information about german newspapers, radio and tv stations and
online services. 

This archive stores a daily snapshot of their undocumented 
json web API. The files are:

- `docs/data/media.json` (from https://medienvielfaltsmonitor.de/api/v1/media/)
  
  This is a list of all medias in the KEK database. 
  
- `docs/data/shareholders.json` (from https://medienvielfaltsmonitor.de/api/v1/shareholders/)

  That's the list of all shareholders and operators/publishers.
  
  All media and shareholders are identified by UUIDs and more
  detailed information for each *entity* is available 
  in the following files:

- `docs/data/media/` 
  - `5be1a6b1-0a0b-42ac-b845-1914e17d572f.json` (from https://medienvielfaltsmonitor.de/api/v1/media/5be1a6b1-0a0b-42ac-b845-1914e17d572f)
  - ...
- `docs/data/shareholders/` 
  - `5be1a6b6-0a00-491b-9229-bfd0da590573.json` (from https://medienvielfaltsmonitor.de/api/v1/shareholders/5be1a6b6-0a00-491b-9229-bfd0da590573)
  - ...

All data is copyright:
[*Kommission zur Ermittlung der Konzentration im Medienbereich (KEK)*](https://www.kek-online.de/impressum).

---

## Data Schemas

Comprehensive schemas for the KEK data are available in the [`schemas/`](schemas/) directory:

- **[JSON Schema](schemas/)** - Formal validation schemas for media and shareholder entities
- **[PostgreSQL Schema](schemas/postgresql-schema.sql)** - Complete relational database schema with 14 tables
- **[Documentation](schemas/README.md)** - Detailed field descriptions and data model
- **[Summary](schemas/SUMMARY.md)** - Comprehensive overview with statistics
- **[Examples](schemas/EXAMPLES.md)** - Practical usage examples and sample queries
- **[Diagram](schemas/DIAGRAM.md)** - Visual representation of entity relationships

Tools:
```bash
python validate_schemas.py --sample 10  # Validate sample files
python import_to_postgres.py --db kek --sample 100  # Import to PostgreSQL
```

---

To build the complete graph of shareholders and media, you need
to parse the individual files in `docs/data/shareholders/` or load
the `docs/data/graph.dot` file. The `dot` format for graphs is 
widely supported, for example by:

- The [Graphviz](https://graphviz.org/) commandline tools
- The [igraph](https://igraph.org/) library for R, Python, Mathematica and C
- The [vis.js](https://visjs.org/) library for Javascript
- The [Gephi](https://gephi.org/) application for Mac, Windows and Linux

From my experience, the fastest way of layouting the graph is Gephi:
Load the dot file, select "ForceAtlas2" in the "Layouter" and "run"
the thing.

