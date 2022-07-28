# THIS REPO IS ARCHIVED

# NGINX will not be supporting this project in any way. This includes not fixing any security vulnerabilities

NGINX plugin for New Relic

## Preface

Visualize performance metrics in New Relic for the open source NGINX software and NGINX Plus.

It allows to collect and report various important counters from an NGINX instance such as:

  * Active client connections
  * Idle (keepalive) client connections
  * Client connections accept rate, drop rate
  * Request rate

NGINX Plus customers will be able to use additional set of metrics
related to upstream monitoring (a number of servers, breakdown by state;
upstream servers connections; bandwidth usage; backend response rate,
breakdown by HTTP status code; healthchecks status), virtual servers
summary stats (requests/responses rate, bandwidth usage), cache zone
stats (responses by cache status, traffic from cache).

Metrics will be charted in the New Relic User Interface and you will be able
to configure alerts based on the values reported by this plugin.

## Requirements

In order to use this plugin, you must have an active New Relic account.

Plugin should work on any generic Unix environment with the following
software components installed:

  * Python (2.6, 2.7)
  * python-daemon
  * make
  * **For CentOS/RHEL only:** initscripts
  * python-setproctitle (optional)

### Requirement for RHEL/CentOS build

  * rpm-build

### Requirements for Debian/Ubuntu build

  * dpkg-dev
  * debhelper

## Build

You can build this tool for rpm or debian using the Makefile. Output will be in the `build_output/` directory.


```console
$ make rpm
```

```console
$ make debian
```

## Configuration

### NGINX

To configure this plugin to work with the open source NGINX software using ngx_http_stub_status
module (http://nginx.org/en/docs/http/ngx_http_stub_status_module.html),
you have to special location containing "stub_status" directive, e.g.:

  Example #1: listen on localhost, access from 127.0.0.1 only:

```nginx
server {
    listen 127.0.0.1:80;
    server_name localhost;

    location = /nginx_stub_status {
        stub_status on;
        allow 127.0.0.1;
        deny all;
    }
}
```

  Example #2: listen on `*:80`, access limited by HTTP basic auth:

```nginx
server {
    listen 80;
    server_name example.com;

    location = /nginx_stub_status {
        stub_status on;
        auth_basic "nginx status";
        auth_basic_user_file /path/to/auth_file;
    }
}
```

  Please follow this link to get more information about HTTP basic auth:
  http://nginx.org/en/docs/http/ngx_http_auth_basic_module.html


### NGINX Plus

To configure this plugin to work with NGINX Plus using api
module (http://nginx.org/en/docs/http/ngx_http_api_module.html),
you have to add special location containing "api" directive, e.g.:

  Example #1: for NGINX Plus status, listen on `*:80`, authorized access:

```nginx
server {
    listen 80;
    server_name example.com;

    location /api {
        api;
        auth_basic "nginx api";
        auth_basic_user_file /path/to/auth_file;
    }
}
```

  (see http://nginx.org/en/docs/http/ngx_http_api_module.html#api for details)

  Do not forget to reload nginx after changing the configuration.


### Plugin configuration

Edit nginx-nr-agent.ini configuration file:

  * insert your New Relic license key.

  * configure data sources (your nginx instances) using the following parameters:
    * url (required): full URL pointing to stub_status (open source NGINX software) or api (NGINX Plus) output.
    * name (required): name of the instance as it will be shown in the New Relic UI.
    * http_user, http_pass (optional): credentials used for
      HTTP basic authorization.


### Configuring HTTPS proxy to access New Relic API endpoint

In case when a host with nginx-nr-agent plugin is behind a proxy,
there is an ability to add proxy URL to the startup configuration script:
  * /etc/sysconfig/nginx-nr-agent in RHEL/CentOS.
  * /etc/default/nginx-nr-agent in Debian/Ubuntu.

It should be done in a form of exporting the HTTPS_PROXY variable, e.g.:
export HTTPS_PROXY="your-proxy-host.example.com:3128"


## Running the plugin

Plugin can be started as a daemon (default) or in foreground mode.
In order to start it daemonized, use the following command under root:

```console
$ service nginx-nr-agent start
```

By default, plugin is running under "nobody" user, writing log
into /var/log/nginx-nr-agent.log.

Plugin status can be checked by running:

```console
$ service nginx-nr-agent status
```

To stop plugin, use:

```console
$ service nginx-nr-agent stop
```

For debugging purposes, you can launch the plugin in foreground mode,
with all output going to stdout:

```console
$ nginx-nr-agent.py -f start
```

Carefully check plugin's output for any possible error messages.
In case of success, collected data should appear in the New Relic
user interface shortly after starting.

## Support
This tool will work with NGINX version R13 and above but support and maintenance of this project will stop at R16
