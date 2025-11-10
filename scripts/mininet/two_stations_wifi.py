import os

from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd, mesh
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

# File paths
PCAP_FILE = './sniff_ota.pcap'
TCPDUMP_LOG_FILE = './sn1_tcpdump.log'

def build_and_run_topology():
    setLogLevel('info')
    # Use wmediumd with interference so frames traverse the "air"
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    # Positions help Mininet-WiFi decide associations; keep sniffer near the path
    sta1 = net.addStation('sta1', ip='10.0.0.1/24', position='10,30,0')
    ap1  = net.addAccessPoint('ap1', ssid='ssid-wifi', mode='g', channel='1', position='20,30,0')
    sn1  = net.addStation('sn1', ip='10.0.0.254/24', position='15,28,0')  # sniffer (IP not really needed)

    c1 = net.addController('c1')

    info("*** Configuring wifi nodes\n")
    # Optional propagation model (helps emulate distance/attenuation)
    net.setPropagationModel(model="logDistance", exp=4)
    net.configureWifiNodes()

    info("*** Starting network\n")
    net.build()
    c1.start()
    ap1.start([c1])

    # --- Disable IPv6 ---
    for node in [sta1, sn1, ap1]:
        node.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        node.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")

    # OPTIONAL: visualize positions (requires X/GUI). Comment out if headless.
    # net.plotGraph(max_x=100, max_y=100)

    sn1_wlan = 'sn1-wlan0'
    mon_if   = 'sn1-mon0' # dedicated monitor interface
    chan     = 1

    info(f'*** Configuring sniffer monitor mode on channel {chan}\n')

    # Clean up if it already exists (safe to ignore errors)
    sn1.cmd(f'ip link set {mon_if} down >/dev/null 2>&1 || true')
    sn1.cmd(f'iw dev {mon_if} del >/dev/null 2>&1 || true')

    # Add monitor interface and bring it up on the AP channel
    sn1.cmd(f'iw dev {sn1_wlan} interface add {mon_if} type monitor')
    sn1.cmd(f'ip link set {mon_if} up')
    sn1.cmd(f'iw dev {mon_if} set channel {chan}')

    # Start tcpdump to capture raw 802.11 (radiotap) frames
    pcap_path = PCAP_FILE
    # -I (rfmon hint) is safe even though iface is already monitor; -s 0 = no snaplen truncation
    sn1.cmd(f'tcpdump -s 0 -i {mon_if} -w {pcap_path} > {TCPDUMP_LOG_FILE} 2>&1 &')
    info(f"*** Sniffer running on {mon_if}; writing to {pcap_path}\n")

    info(f"*** Sniffer running on {sn1_wlan}; writing to {pcap_path}\n")
    info("*** Ready. In another terminal you can stream to sta1/ap1.\n")
    info("*** When done, exit the CLI; we will stop tcpdump automatically.\n")

    # Drop to CLI so you can run your traffic (ffmpeg, ping, etc.)
    CLI(net)

    info("exit command received")

    info("*** Stopping sniffer and deleting monitor interface\n")
    sn1.cmd('pkill -f "tcpdump -s 0 -i sn1-mon0"')
    sn1.cmd('ip link set sn1-mon0 down || true')
    sn1.cmd('iw dev sn1-mon0 del || true')

    info("*** Stopping network\n")
    net.stop()

if __name__ == "__main__":
    # delete existing files
    for filepath in [TCPDUMP_LOG_FILE, PCAP_FILE]:
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    build_and_run_topology()

    with open(TCPDUMP_LOG_FILE) as f:
        print(f.read())

    print("\nDone!")
