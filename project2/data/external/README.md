# Dados Externos (External Data)

Este diretório contém bases de conhecimento e vocabulários controlados de terceiros utilizados para apoiar a extração e a vinculação ontológica:

1. **`anatomical_site_gazetteer.csv`**:
   - Dicionário de estruturas e sítios anatômicos para ancoragem de menções `AnatomicalSite`.

2. **MeSH (Medical Subject Headings — NLM 2026)**:
   - Vocabulário biomédico controlado usado para associar descritores e códigos únicos aos nós de tipo `Concept` (`D...`).
   - Disponível em `project1/src/dicionarios/gazetteer/mesh_gazetteer.csv` (11 MB) ou via distribuição oficial da U.S. National Library of Medicine.
