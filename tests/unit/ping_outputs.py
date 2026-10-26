"""What `ping -c 3 -W 2 1.1.1.1` answers on a phone, as the probe's shell hands it over.

The probe (`taktik/core/shared/device/network_probe.py`) joins the command's stdout and stderr, so a
text here is the two together. Read by the probe's tests and by the network watch's, which decide on
the same measures: one copy of each answer.

Imported as `unit.ping_outputs` (the `tests` folder is on the path of every pytest run, as the
package of `tests/unit/conftest.py`).
"""

#: Three replies, with the summary line.
PING_COMPLET = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=23.4 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=24.9 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=57 time=26.4 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 23.418/24.905/26.377/1.207 ms"""

#: toybox does not always print the summary line; the per-packet times are still there.
PING_SANS_RESUME = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=100.0 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=200.0 ms"""

#: A route, and nothing comes back.
PING_TOUT_PERDU = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2015ms"""

#: No route at all: no mobile data, no Wi-Fi. Taken on a C57S (Android 14) in October 2026, airplane
#: mode and Wi-Fi off: this line on stderr, nothing on stdout, exit code 2.
PING_INJOIGNABLE = "connect: Network is unreachable"

#: A shell without ping: an output the probe cannot read.
PING_ABSENT = "/system/bin/sh: ping: not found"
