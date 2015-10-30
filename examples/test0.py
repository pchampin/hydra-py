"""
Example from the README
"""
def main():
    the_iri_of_the_resource = 'http://www.markus-lanthaler.com/hydra/event-api/'

    from hydra import Resource, SCHEMA
    res = Resource.from_iri(the_iri_of_the_resource)

    print(res)

    print("\nApi documentation:")
    for supcls in res.api_documentation.supported_classes:
        print("  %s" % supcls.identifier)
        for supop in supcls.supported_operations:
            print("    %s" % supop.identifier)
    print("")

    create_event = res.find_suitable_operation(SCHEMA.AddAction, SCHEMA.Event)
    resp, body = create_event({
        "@context": "http://schema.org/",
        "@type": "http://schema.org/Event",
        "name": "Halloween",
        "description": "This is halloween, this is halloween",
        "startDate": "2015-10-31T00:00:00Z",
        "endDate": "2015-10-31T23:59:59Z",
    })
    assert resp.status == 201, "%s %s" % (resp.status, resp.reason)
    new_event = Resource.from_iri(resp['location'])

    print(new_event)


if __name__ == "__main__":
    main()