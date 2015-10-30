"""
A test with Markus' demo.
"""
from datetime import datetime, timedelta
import logging
from rdflib import Graph
import sys
logging.basicConfig(level=logging.WARNING)

from hydra import ApiDocumentation, HYDRA, Resource, SCHEMA


URL = 'http://www.markus-lanthaler.com/hydra/event-api/'
if len(sys.argv) > 1:
    URL = sys.argv[1]

entrypoint = ApiDocumentation.from_iri(URL)

print "All operations:"

for op in entrypoint.all_operations:
    print op.identifier, op.method, op.target_iri

print "\nCreating new event"
add_event = entrypoint.find_suitable_operation(SCHEMA.AddAction, SCHEMA.Event)
start = datetime.utcnow()
end = (start + timedelta(0,1))
resp, body = add_event({
  "@context": "http://www.markus-lanthaler.com/hydra/event-api/contexts/Event.jsonld",
  "@type": "Event",
  "name": "Testing hydra-py",
  "description": "In the process of testing hyda-py",
  "start_date": start.isoformat()[:19] + 'Z',
  "end_date": end.isoformat()[:19] + 'Z',
})
if resp.status != 201:
    print "failed... (%s %s)" % (resp.status, resp.reason)
evt = Resource.from_iri(resp['location'])
print evt.identifier


print "\nUpdating event"
evt.set(SCHEMA.description, evt.value(SCHEMA.description)+" (updated)")
update_event = evt.find_suitable_operation(SCHEMA.UpdateAction, SCHEMA.Event)
resp, body = update_event(evt.graph.default_context)
if resp.status // 100 != 2:
    print "failed... (%s %s)" % (resp.status, resp.reason)
else:
    print "succeeded"
    exit()
print "trying again with ad-hoc JSON"
resp, body = update_event({
  "@context": "http://www.markus-lanthaler.com/hydra/event-api/contexts/Event.jsonld",
  "@type": "Event",
  "@id": unicode(evt.identifier),
  "name": unicode(evt.value(SCHEMA.name)),
  "description": unicode(evt.value(SCHEMA.description)),
  "start_date": unicode(evt.value(SCHEMA.startDate)),
  "end_date": unicode(evt.value(SCHEMA.endDate)),
})
if resp.status // 100 != 2:
    print "failed... (%s %s)" % (resp.status, resp.reason)
else:
    print "succeeded"
