#
Summary: New Relic agent for NGINX and NGINX Plus
Name: nginx-nr-agent
Version: 2.0.1
Release: 1%{?dist}.ngx
Vendor: Nginx Software, Inc.
URL: https://www.nginx.com/
Packager: Nginx Software, Inc. <https://www.nginx.com>

Source0: nginx-nr-agent.py
Source1: nginx-nr-agent.ini
Source2: nginx-nr-agent.init
Source3: COPYRIGHT
Source4: nginx-nr-agent.logrotate
Source5: nginx-nr-agent.sysconfig

License: 2-clause BSD-like license
Group: System Environment/Daemons

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
Requires: python >= 2.6
Requires: python-daemon
Requires: initscripts >= 8.36
Requires(post): chkconfig

BuildArch: noarch

%description
This package contains agent script used for collecting
and reporting a number of metrics from NGINX and/or NGINX Plus
instances to New Relic.

%prep

%build

%install
%{__rm} -rf $RPM_BUILD_ROOT

%{__mkdir} -p $RPM_BUILD_ROOT%{_bindir}
%{__install} -m 755 -p %{SOURCE0} $RPM_BUILD_ROOT%{_bindir}/

%{__mkdir} -p $RPM_BUILD_ROOT%{_sysconfdir}/nginx-nr-agent
%{__install} -m 644 -p %{SOURCE1} $RPM_BUILD_ROOT%{_sysconfdir}/nginx-nr-agent/

%{__mkdir} -p $RPM_BUILD_ROOT%{_datadir}/doc/nginx-nr-agent
%{__install} -m 644 -p %{SOURCE3} \
    $RPM_BUILD_ROOT%{_datadir}/doc/nginx-nr-agent/

%{__mkdir} -p $RPM_BUILD_ROOT%{_initrddir}
%{__install} -m755 %{SOURCE2} \
   $RPM_BUILD_ROOT%{_initrddir}/nginx-nr-agent

%{__mkdir} -p $RPM_BUILD_ROOT%{_sysconfdir}/logrotate.d
%{__install} -m 644 -p %{SOURCE4} \
   $RPM_BUILD_ROOT%{_sysconfdir}/logrotate.d/nginx-nr-agent

%{__mkdir} -p $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig
%{__install} -m 755 -p %{SOURCE5} \
		$RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/nginx-nr-agent

%clean
%{__rm} -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/nginx-nr-agent.py

%{_initrddir}/nginx-nr-agent

%dir %{_sysconfdir}/nginx-nr-agent
%config(noreplace) %{_sysconfdir}/nginx-nr-agent/nginx-nr-agent.ini
%config(noreplace) %{_sysconfdir}/logrotate.d/nginx-nr-agent
%config(noreplace) %{_sysconfdir}/sysconfig/nginx-nr-agent

%dir %{_datadir}/doc/nginx-nr-agent
%{_datadir}/doc/nginx-nr-agent/*

%post
if [ $1 -eq 1 ]; then
    /sbin/chkconfig --add nginx-nr-agent
    mkdir -p /var/run/nginx-nr-agent
    touch /var/log/nginx-nr-agent.log
    chown nobody /var/run/nginx-nr-agent /var/log/nginx-nr-agent.log
    cat <<BANNER
----------------------------------------------------------------------

Thanks for using NGINX!

NGINX agent for New Relic is installed. Configuration file is:
%{_sysconfdir}/nginx-nr-agent/nginx-nr-agent.ini

Please use "service nginx-nr-agent" to control the agent daemon.

More information about NGINX products is available on:
* https://www.nginx.com/

----------------------------------------------------------------------
BANNER
fi

%preun
if [ $1 -eq 0 ]; then
    /sbin/service nginx-nr-agent stop > /dev/null 2>&1
    /sbin/chkconfig --del nginx-nr-agent
fi

%changelog
* Wed Aug  8 2018 Andrei Belov <defan@nginx.com>
- 2.0.1_1
- legacy status module support removed
- new nginx-plus API support added

* Tue Apr 18 2017 Andrei Belov <defan@nginx.com>
- 2.0.0_12
- avoid exiting on unhandled errors while fetching status

* Mon Jan  9 2017 Andrei Belov <defan@nginx.com>
- 2.0.0_11
- upstream keepalive connections metric reintroduced

* Wed Aug 17 2016 Andrei Belov <defan@nginx.com>
- 2.0.0_10
- lock permissions adjusted

* Mon Feb  1 2016 Andrei Belov <defan@nginx.com>
- 2.0.0_9
- fixed handling of caches configured without the "max_size" parameter
- added support for HTTPS proxy

* Mon Sep 21 2015 Andrei Belov <defan@nginx.com>
- 2.0.0_8
- made compatible with nginx-plus-r7 (peer stats moved)

* Mon Apr  6 2015 Andrei Belov <defan@nginx.com>
- 2.0.0_7
- made compatible with nginx-plus-r6 (per-peer keepalive counter removed)

* Wed Mar 25 2015 Andrei Belov <defan@nginx.com>
- 2.0.0_6
- init script fixed for systems without setproctitle Python module

* Tue Mar 10 2015 Andrei Belov <defan@nginx.com>
- 2.0.0_5
- bundled documentation announced in post-install banner

* Tue Oct 31 2014 Andrei Belov <defan@nginx.com>
- 2.0.0_4
- fixed ZeroDivisionError while calculating cache hit ratios

* Tue Oct 21 2014 Andrei Belov <defan@nginx.com>
- 2.0.0_3
- fixed pidfile handling between reboots

* Fri Oct 17 2014 Andrei Belov <defan@nginx.com>
- 2.0.0_2
- fixed Content-Type header recognition

* Wed Sep 10 2014 Andrei Belov <defan@nginx.com>
- 2.0.0
- refactored from previous Ruby-based version to Python
- provides more metrics for N+ (server zones, caches)
