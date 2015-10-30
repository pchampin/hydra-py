"""
Examine a given collection for a hydra:search property,
and dumps the corresponding IRI template.
"""

import sys
import logging
logging.basicConfig(level=logging.INFO)

import hydra

URL = 'http://data.linkeddatafragments.org/dbpedia2014#dataset'
if len(sys.argv) > 1:
    URL = sys.argv[1]

collec = hydra.Collection.from_iri(URL)
#print collec.graph.serialize(format="nquads") + "\n--------\n"

print "COLLECTION: " + collec.identifier
print list(collec[hydra.HYDRA.search])
for st in collec.iri_templates:
    print "  SEARCH TEMPLATE: " + st.identifier.n3()
    print "    template: ", st.template
    print "    tpl_type: ", st.template_type
    print "    vat_repr: ", st.variable_representation
    example = {}
    for m in st.mappings:
        print "      VARIABLE: ", m.variable
        print "        property: ", m.property
        print "        required: ", m.required
        example[m.property] = m.variable[0] + " " + m.variable[-1]
    print "    EXAMPLE: ", st.generate_iri(example)

