#!/bin/sh
### BEGIN INIT INFO
# Provides:          nginx-nr-agent
# Required-Start:    $network $remote_fs $local_fs 
# Required-Stop:     $network $remote_fs $local_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Stop/start nginx-nr-agent
### END INIT INFO

PATH=/sbin:/usr/sbin:/bin:/usr/bin
DESC=nginx-nr-agent
NAME=nginx-nr-agent
CONFFILE=/etc/nginx-nr-agent/nginx-nr-agent.ini
DAEMON=/usr/bin/nginx-nr-agent.py
PIDFILE=/var/run/nginx-nr-agent/$NAME.pid
SCRIPTNAME=/etc/init.d/$NAME

[ -x $DAEMON ] || exit 0

DAEMON_ARGS="-c $CONFFILE -p $PIDFILE"

sysconfig=`/usr/bin/basename $SCRIPTNAME`

. /lib/init/vars.sh

. /lib/lsb/init-functions

[ -r /etc/default/$sysconfig ] && . /etc/default/$sysconfig

do_start()
{
    mkdir -p /var/run/nginx-nr-agent && chown nobody /var/run/nginx-nr-agent
    start-stop-daemon --start --quiet --chuid nobody --exec $DAEMON -- $DAEMON_ARGS start
    RETVAL="$?"
    return "$RETVAL"
}

do_stop()
{
    start-stop-daemon --stop --quiet --oknodo --retry=TERM/30/KILL/5 --pidfile $PIDFILE --name $NAME
    RETVAL="$?"
    rm -f $PIDFILE
    return "$RETVAL"
}

do_configtest() {
    $DAEMON $DAEMON_ARGS configtest
    RETVAL="$?"
    return $RETVAL
}

case "$1" in
    start)
	do_configtest || exit 1
        [ "$VERBOSE" != no ] && log_daemon_msg "Starting $DESC " "$NAME"
        do_start
        case "$?" in
            0|1) [ "$VERBOSE" != no ] && log_end_msg 0 ;;
            2) [ "$VERBOSE" != no ] && log_end_msg 1 ;;
        esac
        ;;
    stop)
        [ "$VERBOSE" != no ] && log_daemon_msg "Stopping $DESC" "$NAME"
        do_stop
        case "$?" in
            0|1) [ "$VERBOSE" != no ] && log_end_msg 0 ;;
            2) [ "$VERBOSE" != no ] && log_end_msg 1 ;;
        esac
        ;;
    status)
        status_of_proc -p "$PIDFILE" "$DAEMON" "$NAME" && exit 0 || exit $?
        ;;
    configtest)
        do_configtest
        ;;
    restart|force-reload)
        log_daemon_msg "Restarting $DESC" "$NAME"
        do_configtest || exit 1
        do_stop
        case "$?" in
            0|1)
                do_start
                case "$?" in
                    0) log_end_msg 0 ;;
                    1) log_end_msg 1 ;; # Old process is still running
                    *) log_end_msg 1 ;; # Failed to start
                esac
                ;;
            *)
                # Failed to stop
                log_end_msg 1
                ;;
        esac
        ;;
    *)
        echo "Usage: $SCRIPTNAME {start|stop|status|restart|configtest}" >&2
        exit 3
        ;;
esac

exit $RETVAL
