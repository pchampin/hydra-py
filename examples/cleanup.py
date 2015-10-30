"""
Example from the README
"""

import logging

logging.basicConfig(level=logging.INFO)

def main():

    from hydra import Collection, Resource, SCHEMA
    res = Collection.from_iri("http://www.markus-lanthaler.com/hydra/event-api/events/")
    print res

    for i in res.members:
        # below, we must force to load each member,
        # because the collection contains *some* info about its members,
        # causing the code to assume that *all* info is present in the collection graph
        i = Resource.from_iri(i.identifier)
        name = i.value(SCHEMA.name)
        if "hydra-py" in name or "py-hydra" in name or "Halloween" in name:
            resp, _ = i.find_suitable_operation(SCHEMA.DeleteAction)()
            if resp.status // 100 != 2:
                print("error deleting <%s>" % i.identifier)
            else:
                print("deleted <%s>" % i.identifier)

main()