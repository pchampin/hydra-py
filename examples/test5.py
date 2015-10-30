"""
Use TPFStore and performs a SPARQL query on top of it.
Note that this is very (very!) slow as soon as the query becomes slightly complex... :-/
"""
import logging
from rdflib import Graph
import sys
logging.basicConfig(level=logging.INFO)

import hydra.tpf # required to register TPFStore plugin

URL = 'http://data.linkeddatafragments.org/dbpedia2014'
if len(sys.argv) > 1:
    URL = sys.argv[1]

g = Graph("TPFStore")
g.open(URL)

QUERY = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbr: <http://dbpedia.org/resource/>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT * {
        ?p a dbo:Person; dbo:birthPlace ?bp .
    }
    LIMIT 10
"""

print len(g)

results = g.query(QUERY)
for i in results:
    print i
