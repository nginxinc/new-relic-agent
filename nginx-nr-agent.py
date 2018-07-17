#!/usr/bin/env python
#
# Copyright (C) Andrei Belov
# Copyright (C) Nginx, Inc.
#

import logging, logging.config
import os, re, sys, ConfigParser
import json
import base64
from time import sleep, time
from urllib2 import Request, urlopen, URLError, HTTPError
from daemon import runner
import traceback

NEWRELIC_API_URL = 'https://platform-api.newrelic.com/platform/v1/metrics'
AGENT_GUID = 'com.nginx.newrelic-agent'
AGENT_VERSION = '2.0.0'

DEFAULT_CONFIG_FILE = '/etc/nginx-nr-agent/nginx-nr-agent.ini'
DEFAULT_PID_FILE = '/var/run/nginx-nr-agent/nginx-nr-agent.pid'
DEFAULT_POLL_INTERVAL = 60.0

LOG = logging.getLogger('nginx-nr-agent')

class NginxStatusCollector(object):

    def __init__(self, section, name, url, poll_interval):
	self.section = section
	self.name = name
	self.url = url
	self.basic_auth = None
	self.gauges = dict()
	self.derives = dict()
	self.deltas = dict()
	self.prevupdate = 0.0
	self.lastupdate = 0.0
	self.unpushed = []
	self.poll_interval = poll_interval

    def update_gauge(self, metric, units, value):
	self.gauges[metric] = value
	self.unpushed.append({ 'metric': metric, 'value': value, 'units': units, 'timestamp': self.lastupdate })
	LOG.debug("update gauge %s: rv=%.2f", metric, value)

    def update_derive(self, metric, units, value):
	if metric not in self.derives.keys():
	    self.derives[metric] = value
	    return

	delta = value - self.derives[metric]
	if delta < 0:
	    LOG.info("derive counter for %s was reset, skipping update", metric)
	    self.derives[metric] = value
	    return

	timedelta = float(time() - self.prevupdate) if self.prevupdate else float(self.poll_interval)
	rv = float(delta / timedelta)
	self.unpushed.append({ 'metric': metric, 'value': rv, 'units': units, 'timestamp': self.lastupdate })
	LOG.debug("update derive %s: pv=%d cv=%d rv=%.3f td=%.3f", metric,
		  self.derives[metric], value, rv, timedelta)
	self.derives[metric] = value
	self.deltas[metric] = delta

    def get_status_data(self):
	r = Request(self.url)
	if self.basic_auth:
	    r.add_header('Authorization', "Basic %s" % self.basic_auth)
	try:
	    u = urlopen(r)
	except HTTPError as e:
	    LOG.error("request for %s returned %d", self.url, e.code)
	    return None
	except URLError as e:
	    LOG.error("request for %s failed: %s", self.url, e.reason)
	    return None
	except:
	    LOG.error("EXCEPTION while fetching status: %s", traceback.format_exc())
	    return None
	ct = u.info().getheader('Content-Type')
	return {'content-type': ct, 'body': u.read()}

    def update_base_stats(self, stats):
	# conn/accepted, conn/dropped, conn/active, conn/idle, reqs/total, reqs/current
	self.update_derive('conn/accepted', 'Connections/sec', stats[0])
	self.update_derive('conn/dropped', 'Connections/sec', stats[1])
	self.update_gauge('conn/active', 'Connections', stats[2])
	self.update_gauge('conn/idle', 'Connections', stats[3])
	self.update_derive('reqs/total', 'Requests/sec', stats[4])
	self.update_gauge('reqs/current', 'Requests', stats[5])

    def update_extended_stats(self, js):
	LOG.debug("updating extended metrics for status version %d", js['version'])

	if js.get('upstreams'):
	    LOG.debug("collecting extra metrics for %d upstreams", len(js['upstreams']))

	    u_srv_up, u_srv_down, u_srv_unavail, u_srv_unhealthy = 0, 0, 0, 0
	    u_conn_active, u_conn_keepalive = 0, 0
	    u_reqs, u_resp, u_resp_1xx, u_resp_2xx, u_resp_3xx, u_resp_4xx, u_resp_5xx = 0, 0, 0, 0, 0, 0, 0
	    u_sent, u_received = 0, 0
	    u_fails, u_unavail = 0, 0
	    u_hc_checks, u_hc_fails, u_hc_unhealthy = 0, 0, 0

	    for u in js['upstreams'].itervalues():
		if js['version'] >= 6:
		    u_conn_keepalive += u['keepalive']
		upeers = u if js['version'] < 6 else u['peers']
		for us in upeers:
		    if us['state'] == 'up':
			u_srv_up += 1
		    elif us['state'] == 'down':
			u_srv_down += 1
		    elif us['state'] == 'unavail':
			u_srv_unavail += 1
		    elif us['state'] == 'unhealthy':
			u_srv_unhealthy += 1

		    u_conn_active += us['active']
		    if js['version'] < 5:
			u_conn_keepalive += us['keepalive']
		    u_reqs += us['requests']
		    u_resp += us['responses']['total']
		    u_resp_1xx += us['responses']['1xx']
		    u_resp_2xx += us['responses']['2xx']
		    u_resp_3xx += us['responses']['3xx']
		    u_resp_4xx += us['responses']['4xx']
		    u_resp_5xx += us['responses']['5xx']
		    u_sent += us['sent']
		    u_received += us['received']
		    u_fails += us['fails']
		    u_unavail += us['unavail']
		    u_hc_checks += us['health_checks']['checks']
		    u_hc_fails += us['health_checks']['fails']
		    u_hc_unhealthy += us['health_checks']['unhealthy']

	    self.update_gauge('upstream/servers/up', 'Servers', u_srv_up)
	    self.update_gauge('upstream/servers/down', 'Servers', u_srv_down)
	    self.update_gauge('upstream/servers/unavail', 'Servers', u_srv_unavail)
	    self.update_gauge('upstream/servers/unhealthy', 'Servers', u_srv_unhealthy)

	    self.update_gauge('upstream/conn/active', 'Connections', u_conn_active)
	    self.update_gauge('upstream/conn/keepalive', 'Connections', u_conn_keepalive)

	    self.update_derive('upstream/reqs', 'Requests/sec', u_reqs)
	    self.update_derive('upstream/resp', 'Responses/sec', u_resp)
	    self.update_derive('upstream/resp/1xx', 'Responses/sec', u_resp_1xx)
	    self.update_derive('upstream/resp/2xx', 'Responses/sec', u_resp_2xx)
	    self.update_derive('upstream/resp/3xx', 'Responses/sec', u_resp_3xx)
	    self.update_derive('upstream/resp/4xx', 'Responses/sec', u_resp_4xx)
	    self.update_derive('upstream/resp/5xx', 'Responses/sec', u_resp_5xx)

	    self.update_derive('upstream/traffic/sent', 'Bytes/sec', u_sent)
	    self.update_derive('upstream/traffic/received', 'Bytes/sec', u_received)

	    self.update_gauge('upstream/server/fails', 'times', u_fails)
	    self.update_gauge('upstream/server/unavails', 'times', u_unavail)
	    self.update_gauge('upstream/hc/total', 'times', u_hc_checks)
	    self.update_gauge('upstream/hc/fails', 'times', u_hc_fails)
	    self.update_gauge('upstream/hc/unhealthies', 'times', u_hc_unhealthy)

	if js.get('server_zones'):
	    LOG.debug("collecting extra metrics for %d server_zones", len(js['server_zones']))

	    sz_processing, sz_requests, sz_received, sz_sent = 0, 0, 0, 0
	    sz_resp, sz_resp_1xx, sz_resp_2xx, sz_resp_3xx, sz_resp_4xx, sz_resp_5xx = 0, 0, 0, 0, 0, 0

	    for sz in js['server_zones'].itervalues():
		sz_processing += sz['processing']
		sz_requests += sz['requests']
		sz_received += sz['received']
		sz_sent += sz['sent']
		sz_resp += sz['responses']['total']
		sz_resp_1xx += sz['responses']['1xx']
		sz_resp_2xx += sz['responses']['2xx']
		sz_resp_3xx += sz['responses']['3xx']
		sz_resp_4xx += sz['responses']['4xx']
		sz_resp_5xx += sz['responses']['5xx']

	    self.update_gauge('sz/processing', 'Requests', sz_processing)
	    self.update_derive('sz/requests', 'Requests/sec', sz_requests)
	    self.update_derive('sz/received', 'Bytes/sec', sz_received)
	    self.update_derive('sz/sent', 'Bytes/sec', sz_sent)
	    self.update_derive('sz/resp', 'Responses/sec', sz_resp)
	    self.update_derive('sz/resp/1xx', 'Responses/sec', sz_resp_1xx)
	    self.update_derive('sz/resp/2xx', 'Responses/sec', sz_resp_2xx)
	    self.update_derive('sz/resp/3xx', 'Responses/sec', sz_resp_3xx)
	    self.update_derive('sz/resp/4xx', 'Responses/sec', sz_resp_4xx)
	    self.update_derive('sz/resp/5xx', 'Responses/sec', sz_resp_5xx)

	if js.get('caches'):
	    LOG.debug("collecting extra metrics for %d caches", len(js['caches']))

	    cache_size, cache_max_size = 0, 0
	    cache_resp_hit, cache_resp_stale, cache_resp_updating, cache_resp_revalidated = 0, 0, 0, 0
	    cache_bytes_hit, cache_bytes_stale, cache_bytes_updating, cache_bytes_revalidated = 0, 0, 0, 0
	    cache_resp_miss, cache_resp_expired, cache_resp_bypass = 0, 0, 0
	    cache_bytes_miss, cache_bytes_expired, cache_bytes_bypass = 0, 0, 0
	    cache_resp_written_miss, cache_resp_written_expired, cache_resp_written_bypass = 0, 0, 0
	    cache_bytes_written_miss, cache_bytes_written_expired, cache_bytes_written_bypass = 0, 0, 0

	    for c in js['caches'].itervalues():
		cache_size += c['size']
		cache_max_size += c.get('max_size', 0)
		cache_resp_hit += c['hit']['responses']
		cache_resp_stale += c['stale']['responses']
		cache_resp_updating += c['updating']['responses']
		cache_resp_revalidated += c['revalidated']['responses']
		cache_bytes_hit += c['hit']['bytes']
		cache_bytes_stale += c['stale']['bytes']
		cache_bytes_updating += c['updating']['bytes']
		cache_bytes_revalidated += c['revalidated']['bytes']
		cache_resp_miss += c['miss']['responses']
		cache_resp_expired += c['expired']['responses']
		cache_resp_bypass += c['bypass']['responses']
		cache_bytes_miss += c['miss']['bytes']
		cache_bytes_expired += c['expired']['bytes']
		cache_bytes_bypass += c['bypass']['bytes']
		cache_resp_written_miss += c['miss']['responses_written']
		cache_resp_written_expired += c['expired']['responses_written']
		cache_resp_written_bypass += c['bypass']['responses_written']
		cache_bytes_written_miss += c['miss']['bytes_written']
		cache_bytes_written_expired += c['expired']['bytes_written']
		cache_bytes_written_bypass += c['bypass']['bytes_written']

	    self.update_gauge('cache/size', 'Bytes', cache_size)
	    self.update_gauge('cache/max_size', 'Bytes', cache_max_size)
	    self.update_derive('cache/resp/hit', 'Responses/sec', cache_resp_hit)
	    self.update_derive('cache/resp/stale', 'Responses/sec', cache_resp_stale)
	    self.update_derive('cache/resp/updating', 'Responses/sec', cache_resp_updating)
	    self.update_derive('cache/resp/revalidated', 'Responses/sec', cache_resp_revalidated)
	    self.update_derive('cache/bytes/hit', 'Bytes/sec', cache_bytes_hit)
	    self.update_derive('cache/bytes/stale', 'Bytes/sec', cache_bytes_stale)
	    self.update_derive('cache/bytes/updating', 'Bytes/sec', cache_bytes_updating)
	    self.update_derive('cache/bytes/revalidated', 'Bytes/sec', cache_bytes_revalidated)
	    self.update_derive('cache/resp/miss', 'Responses/sec', cache_resp_miss)
	    self.update_derive('cache/resp/expired', 'Responses/sec', cache_resp_expired)
	    self.update_derive('cache/resp/bypass', 'Responses/sec', cache_resp_bypass)
	    self.update_derive('cache/bytes/miss', 'Bytes/sec', cache_bytes_miss)
	    self.update_derive('cache/bytes/expired', 'Bytes/sec', cache_bytes_expired)
	    self.update_derive('cache/bytes/bypass', 'Bytes/sec', cache_bytes_bypass)
	    self.update_derive('cache/resp_written/miss', 'Responses/sec', cache_resp_written_miss)
	    self.update_derive('cache/resp_written/expired', 'Responses/sec', cache_resp_written_expired)
	    self.update_derive('cache/resp_written/bypass', 'Responses/sec', cache_resp_written_bypass)
	    self.update_derive('cache/bytes_written/miss', 'Bytes/sec', cache_bytes_written_miss)
	    self.update_derive('cache/bytes_written/expired', 'Bytes/sec', cache_bytes_written_expired)
	    self.update_derive('cache/bytes_written/bypass', 'Bytes/sec', cache_bytes_written_bypass)

	    cache_resp_cached = cache_resp_hit + cache_resp_stale + cache_resp_updating + cache_resp_revalidated
	    cache_resp_uncached = cache_resp_miss + cache_resp_expired + cache_resp_bypass
	    if (cache_resp_cached + cache_resp_uncached) > 0:
		cache_hit_ratio_long = (cache_resp_cached / float(cache_resp_cached + cache_resp_uncached)) * 100.0
		self.update_gauge('cache/hitratio/long', 'Percent', cache_hit_ratio_long)

	    if 'cache/resp/hit' in self.deltas.keys():
		cache_resp_cached = (self.deltas['cache/resp/hit'] + self.deltas['cache/resp/stale'] +
				     self.deltas['cache/resp/updating'] + self.deltas['cache/resp/revalidated'])
		cache_resp_uncached = (self.deltas['cache/resp/miss'] + self.deltas['cache/resp/expired'] +
				       self.deltas['cache/resp/bypass'])
		if (cache_resp_cached + cache_resp_uncached) > 0:
		    cache_hit_ratio_short = (cache_resp_cached / float(cache_resp_cached + cache_resp_uncached)) * 100.0
		    self.update_gauge('cache/hitratio/short', 'Percent', cache_hit_ratio_short)

    def process_stub_status(self, body):
	LOG.debug("processing stub status for %s", self.name)
	STUB_RE = re.compile(r'^Active connections: (?P<connections>\d+)\s+[\w ]+\n'
                  r'\s+(?P<accepts>\d+)'
                  r'\s+(?P<handled>\d+)'
                  r'\s+(?P<requests>\d+)'
                  r'\s+Reading:\s+(?P<reading>\d+)'
                  r'\s+Writing:\s+(?P<writing>\d+)'
                  r'\s+Waiting:\s+(?P<waiting>\d+)')
	m = STUB_RE.match(body)
	if not m:
	    LOG.error("could not parse stub status body (len=%d): '%s'", len(body), body)
	    return False
	self.lastupdate = time()
	self.update_base_stats([
		int(m.group('accepts')),
		int(m.group('accepts')) - int(m.group('handled')),
		int(m.group('connections')),
		int(m.group('waiting')),
		int(m.group('requests')),
		int(m.group('reading')) + int(m.group('writing'))])
	return True

    def process_new_status(self, body):
	LOG.debug("processing new status for %s", self.name)
	try:
	    js = json.loads(body)
	except ValueError, e:
	    LOG.error("could not parse JSON from new status body: '%s'", body)
	    return False
	self.lastupdate = time()
	self.update_base_stats([
		js['connections']['accepted'],
		js['connections']['dropped'],
		js['connections']['active'],
		js['connections']['idle'],
		js['requests']['total'],
		js['requests']['current']])
	self.update_extended_stats(js)
	return True

    def poll(self):
	LOG.debug("getting data from %s (lastupdate=%.3f)", self.url, self.lastupdate)
	data = self.get_status_data()
	if data is None:
	    LOG.error("get_status_data() returned nothing to process")
	    return False
	if data['content-type'].startswith('text/plain'):
	    rc = self.process_stub_status(data['body'])
	elif data['content-type'].startswith('application/json'):
	    rc = self.process_new_status(data['body'])
	else:
	    LOG.error("unknown Content-Type from %s: '%s'", self.url, data['content-type'])
	    return False
	self.prevupdate = self.lastupdate
	return rc

class NginxNewRelicAgent():

    def __init__(self):
	self.stdin_path = '/dev/null'
	self.stdout_path = '/dev/null'
	self.stderr_path = '/dev/null'
	self.pidfile_path = DEFAULT_PID_FILE
	self.pidfile_timeout = 5
	self.config = None
	self.config_file = DEFAULT_CONFIG_FILE
	self.foreground = False
	self.poll_interval = DEFAULT_POLL_INTERVAL
	self.license_key = None
	self.sources = []
	self.metric_names = {
		'conn/accepted': [ 'Connections/Accepted' ],
		'conn/dropped': [ 'Connections/Dropped' ],
		'conn/active': [ 'Connections/Active', 'ConnSummary/Active' ],
		'conn/idle': [ 'Connections/Idle', 'ConnSummary/Idle' ],
		'reqs/total': [ 'Requests/Total' ],
		'reqs/current': [ 'Requests/Current' ],
		'upstream/servers/up': [ 'UpstreamServers/Up' ],
		'upstream/servers/down': [ 'UpstreamServers/Down' ],
		'upstream/servers/unavail': [ 'UpstreamServers/Unavailable' ],
		'upstream/servers/unhealthy': [ 'UpstreamServers/Unhealthy' ],
		'upstream/conn/active': [ 'UpstreamConnections/Active' ],
		'upstream/conn/keepalive': [ 'UpstreamConnections/Keepalive' ],
		'upstream/reqs': [ 'UpstreamReqsResp/Requests' ],
		'upstream/resp': [ 'UpstreamReqsResp/Responses' ],
		'upstream/resp/1xx': [ 'UpstreamResponses/1xx' ],
		'upstream/resp/2xx': [ 'UpstreamResponses/2xx' ],
		'upstream/resp/3xx': [ 'UpstreamResponses/3xx' ],
		'upstream/resp/4xx': [ 'UpstreamResponses/4xx' ],
		'upstream/resp/5xx': [ 'UpstreamResponses/5xx' ],
		'upstream/traffic/sent': [ 'UpstreamTraffic/Sent' ],
		'upstream/traffic/received': [ 'UpstreamTraffic/Received' ],
		'upstream/server/fails': [ 'UpstreamMisc/ServerFails' ],
		'upstream/server/unavails': [ 'UpstreamMisc/ServerUnavailable' ],
		'upstream/hc/total': [ 'UpstreamMisc/HealthChecksTotal' ],
		'upstream/hc/fails': [ 'UpstreamMisc/HealthChecksFails' ],
		'upstream/hc/unhealthies': [ 'UpstreamMisc/HealthChecksUnhealthy' ],
		'sz/processing': [ 'ServerZone/Processing' ],
		'sz/requests': [ 'ServerZoneReqsResp/Requests' ],
		'sz/resp': [ 'ServerZoneReqsResp/Responses' ],
		'sz/resp/1xx': [ 'ServerZoneResponses/1xx' ],
		'sz/resp/2xx': [ 'ServerZoneResponses/2xx' ],
		'sz/resp/3xx': [ 'ServerZoneResponses/3xx' ],
		'sz/resp/4xx': [ 'ServerZoneResponses/4xx' ],
		'sz/resp/5xx': [ 'ServerZoneResponses/5xx' ],
		'sz/sent': [ 'ServerZoneTraffic/Sent' ],
		'sz/received': [ 'ServerZoneTraffic/Received' ],
		'cache/hitratio/long': [ 'CacheHitRatio/Long' ],
		'cache/hitratio/short': [ 'CacheHitRatio/Short' ],
		'cache/size': [ 'CacheSize/Size' ],
		'cache/max_size': [ 'CacheSize/MaxSize' ],
		'cache/resp/hit': [ 'CachedResponses/Hit' ],
		'cache/resp/stale': [ 'CachedResponses/Stale' ],
		'cache/resp/updating': [ 'CachedResponses/Updating' ],
		'cache/resp/revalidated': [ 'CachedResponses/Revalidated' ],
		'cache/bytes/hit': [ 'CachedBytes/Hit' ],
		'cache/bytes/stale': [ 'CachedBytes/Stale' ],
		'cache/bytes/updating': [ 'CachedBytes/Updating' ],
		'cache/bytes/revalidated': [ 'CachedBytes/Revalidated' ],
		'cache/resp/miss': [ 'UncachedResponses/Miss' ],
		'cache/resp/expired': [ 'UncachedResponses/Expired' ],
		'cache/resp/bypass': [ 'UncachedResponses/Bypass' ],
		'cache/bytes/miss': [ 'UncachedBytes/Miss' ],
		'cache/bytes/expired': [ 'UncachedBytes/Expired' ],
		'cache/bytes/bypass': [ 'UncachedBytes/Bypass' ],
		'cache/resp_written/miss': [ 'UncachedResponsesWritten/Miss' ],
		'cache/resp_written/expired': [ 'UncachedResponsesWritten/Expired' ],
		'cache/resp_written/bypass': [ 'UncachedResponsesWritten/Bypass' ],
		'cache/bytes_written/miss': [ 'UncachedBytesWritten/Miss' ],
		'cache/bytes_written/expired': [ 'UncachedBytesWritten/Expired' ],
		'cache/bytes_written/bypass': [ 'UncachedBytesWritten/Bypass' ]
	}

    def newrelic_push(self):
	components = []
	metrics_total = 0
	for ns in self.sources:
	    if len(ns.unpushed) == 0:
		continue
	    LOG.debug("composing push data for %s (%d entries)", ns.name, len(ns.unpushed))
	    component = dict()
	    metrics = dict()
	    component['guid'] = AGENT_GUID
	    component['duration'] = self.poll_interval
	    component['name'] = ns.name
	    for m in ns.unpushed:
		for mn in self.metric_names[m['metric']]:
		    metrics["Component/%s[%s]" % (mn, m['units'])] = m['value']
		    metrics_total += 1
	    component['metrics'] = metrics
	    components.append(component)
	    del ns.unpushed[:]

	if len(components) == 0:
	    return

	LOG.info("pushing %d metrics for %d components", metrics_total, len(components))

	payload = dict()
	payload['agent'] = { 'version': AGENT_VERSION }
	payload['components'] = components

	LOG.debug("JSON payload: '%s'", json.dumps(payload))

	r = Request(NEWRELIC_API_URL)
	r.add_header('Content-Type', 'application/json')
	r.add_header('Accept', 'application/json')
	r.add_header('User-Agent', "newrelic-nginx-agent/%s" % AGENT_VERSION)
	r.add_header('X-License-Key', self.license_key)

	try:
	    u = urlopen(r, data=json.dumps(payload))
	except HTTPError as e:
	    LOG.error("POST request for %s returned %d", NEWRELIC_API_URL, e.code)
	    LOG.debug("response:\n%s\n%s", e.headers, e.read())
	    return
	except URLError as e:
	    LOG.error("POST request for %s failed: %s", NEWRELIC_API_URL, e.reason)
	    return
	except:
	    LOG.error("EXCEPTION while pushing metrics: %s", traceback.format_exc())
	    return

	response_body = u.read()
	LOG.debug("response:\n%s\n%s", u.headers, response_body)

	try:
	    js = json.loads(response_body)
	except ValueError, e:
	    LOG.error("could not parse JSON from response body: '%s'", response_body)
	    return False

	if js['status'] != 'ok':
	    LOG.error("push failed with status response: %s", js['status'])
	    return False

	LOG.info("pushing finished successfully")
	return True

    def read_config(self):
	if self.config:
	    return

	config = ConfigParser.RawConfigParser()
	config.read(self.config_file)

	for s in config.sections():
	    if s == 'global':
		if config.has_option(s, 'poll_interval'):
		    self.poll_interval = int(config.get(s, 'poll_interval'))
		if config.has_option(s, 'newrelic_license_key'):
		    self.license_key = config.get(s, 'newrelic_license_key')
		continue
	    if not config.has_option(s, 'name') or not config.has_option(s, 'url'):
		continue
	    ns = NginxStatusCollector(s, config.get(s, 'name'), config.get(s, 'url'), self.poll_interval)
	    if config.has_option(s, 'http_user') and config.has_option(s, 'http_pass'):
		ns.basic_auth = base64.b64encode(config.get(s, 'http_user') + b':' + config.get(s, 'http_pass'))
	    self.sources.append(ns)
	self.config = config

    def configtest(self):
	self.read_config()

	if not self.license_key:
	    LOG.error("no license key defined")
	    sys.exit(1)

	if len(self.sources) == 0:
	    LOG.error("no data sources configured - nothing to do")
	    sys.exit(1)

    def run(self):
	LOG.info('using configuration from %s', self.config_file)
	self.configtest()

	LOG.info('starting with %d configured data sources, poll_interval=%d',
		 len(self.sources), self.poll_interval)

	while True:
	    try:
		for ns in self.sources:
		    LOG.info("polling %s", ns.section)
		    if ns.poll():
			LOG.info("polling %s finished successfully", ns.section)
		    else:
			LOG.error("polling %s failed", ns.section)
		self.newrelic_push()
		sleep(self.poll_interval)
	    except KeyboardInterrupt:
		LOG.info("exiting due to KeyboardInterrupt")
		sys.exit(0)
	    except SystemExit:
		LOG.info("exiting")
		sys.exit(0)

class MyDaemonRunner(runner.DaemonRunner):

    def __init__(self, app):
	self._app = app
	self.detach_process = True
	runner.DaemonRunner.__init__(self, app)
        self.daemon_context.umask = 0022
	self.action_funcs['configtest'] = MyDaemonRunner._configtest

    def _configtest(self):
	self._app.configtest()

    def show_usage(self, rc):
	print "usage: %s [options] action" % sys.argv[0]
	print "valid actions: start, stop, configtest"
	print " -c, --config       path to configuration file"
	print " -p, --pidfile      path to pidfile"
	print " -f, --foreground   do not detach from terminal" 
	sys.exit(rc)

    def parse_args(self, argv=None):
	import getopt

	if len(sys.argv) < 2:
	    self.show_usage(0)

	try:
	    opts, args = getopt.getopt(sys.argv[1:], 'c:p:f',
				       ['config=', 'pidfile=', 'foreground'])
	except getopt.GetoptError as e:
	    print "Error: %s" % str(e)
	    sys.exit(1)

	if len(args) == 0:
	    self.show_usage(0)

	self.action = args[0]
	if self.action not in ('start', 'stop', 'configtest'):
	    print "Invalid action: %s" % self.action
	    self.show_usage(1)

	for opt, arg in opts:
	    if opt in ('-c', '--config'):
		self._app.config_file = os.path.abspath(arg)

	    elif opt in ('-p', '--pidfile'):
		self._app.pidfile_path = arg

	    elif opt in ('-f', '--foreground'):
		self.detach_process = False
		self._app.stdout_path = '/dev/tty'
		self._app.stderr_path = '/dev/tty'
		self._app.foreground = True

	    else:
		print "Could not parse option: %s" % opt
		self.show_usage(1)

def getLogFileHandles(logger):
    handles = []
    for handler in logger.handlers:
        handles.append(handler.stream.fileno())
    if logger.parent:
        handles += getLogFileHandles(logger.parent)
    return handles

def main():
    app = NginxNewRelicAgent()
    daemon_runner = MyDaemonRunner(app)

    try:
	from setproctitle import setproctitle
	setproctitle('nginx-nr-agent')
    except ImportError:
	pass

    if not os.path.isfile(app.config_file) or not os.access(app.config_file, os.R_OK):
	print "Config file %s could not be found or opened." % app.config_file
	sys.exit(1)

    try:
	logging.config.fileConfig(app.config_file, None, False)
    except Exception, e:
	print "Error while configuring logging: %s" % e
	sys.exit(1)

    if not app.foreground:
	daemon_runner.daemon_context.files_preserve = getLogFileHandles(LOG)
	daemon_runner.do_action()
    elif daemon_runner.action == 'configtest':
	app.configtest()
    else:
	app.run()

if __name__ == '__main__':
    main()
