"""
Use the tpf module to query a TPF-enabled dataset.
"""
import logging
import sys
from rdflib import Graph, Namespace, RDF, RDFS
logging.basicConfig(level=logging.INFO)

from hydra.tpf import TPFAwareCollection



URL = 'http://data.linkeddatafragments.org/dbpedia2014#dataset'
if len(sys.argv) > 1:
    URL = sys.argv[1]

collec = TPFAwareCollection.from_iri(URL)
#print collec.graph.serialize(format="nquads") + "\n--------\n"

g = Graph()
for i, t in enumerate(collec.iter_triples(None, RDF.type, None)):
    #print i, t
    if i == 350:
        break
    assert t[1] == RDF.type
    g.add(t)
print len(g)