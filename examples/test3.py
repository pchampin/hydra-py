"""
Testing find_suitable_template with background knowledge
"""

import sys
from rdflib import Namespace, RDF, RDFS
import logging
logging.basicConfig(level=logging.INFO)

import hydra


EX = Namespace("http://example.org/")
hydra.BACKGROUND_KNOWLEDGE.add((EX.p, RDFS.subPropertyOf, RDF.predicate))
hydra.BACKGROUND_KNOWLEDGE.add((EX.o, RDFS.subPropertyOf, EX.o2))
hydra.BACKGROUND_KNOWLEDGE.add((EX.o2, RDFS.subPropertyOf, RDF.object))

URL = 'http://data.linkeddatafragments.org/dbpedia2014#dataset'
if len(sys.argv) > 1:
    URL = sys.argv[1]

collec = hydra.Collection.from_iri(URL)
#print collec.graph.serialize(format="nquads") + "\n--------\n"

template = collec.find_suitable_template([RDF.subject, EX.p, EX.o])
print template.generate_iri({ RDF.subject: "X", EX.p: "Y", EX.o: "Z" })
