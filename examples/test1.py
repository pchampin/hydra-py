"""
Dumps the content of an Hydra API documentation.
"""

import logging
import sys
logging.basicConfig(level=logging.WARNING)

import hydra

URL = 'http://www.markus-lanthaler.com/hydra/event-api/'
if len(sys.argv) > 1:
    URL = sys.argv[1]

service = hydra.Resource.from_iri(URL)
#print service.graph.serialize(format="n3") + "\n--------\n"

apidoc = service.api_documentation
assert apidoc is not None

print "SERVICE:", URL
print "API DOC:", apidoc.identifier.n3()
if apidoc.title:
    print "  title:", apidoc.title
print

for cls in apidoc.supported_classes:
    print "SUPPORTED CLASS: ", cls.identifier
    for pr in cls.supported_properties:
        print "  SUPPORTED PROPERTY:", pr.identifier
        print "    property:", pr.property.identifier
        if pr.title:
            print "    title:", pr.title
        print "    required:", pr.required
        print "    readable:", pr.readable
        print "    writeable:", pr.writeable
        print "    readonly:", pr.readonly
        print "    writeonly:", pr.writeonly
        for op in pr.property.supported_operations:
            print "    SUPPORTED OPERATION:", op.identifier.n3()
            if op.title:
                print "      title:", op.title
            print "      method:", op.method
            if op.expected_class:
                print "      expects:", op.expected_class.identifier
            if op.returned_class:
                print "      returns:", op.returned_class.identifier
    for op in cls.supported_operations:
        print "  SUPPORTED OPERATION: ", op.identifier.n3()
        if op.title:
            print "    title:", op.title
        print "    types: ", ",".join(i.n3() for i in op.types)
        print "    method:", op.method
        if op.expected_class:
            print "    expects:", op.expected_class.identifier
        if op.returned_class:
            print "    returns:", op.returned_class.identifier
    print

