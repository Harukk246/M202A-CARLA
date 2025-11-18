import os
import time
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd, mesh
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

# File paths
PCAP_FILE = './sniff_ota.pcap'
TCPDUMP_LOG_FILE = './sn1_tcpdump.log'

UDP_PORT = 5000
VIDEO_PATH = "/home/wifi/carla-project/test2.mp4"

def start_video_stream(sta1, sta2):
    # --- Start video stream from sta1 -> sta2 using ffmpeg over UDP ---
    info("*** Starting ffmpeg receiver on sta2\n")
    sta2.cmd(
        "nohup ffmpeg "
        "-loglevel error "
        f"-i udp://0.0.0.0:{UDP_PORT} "  # listen on UDP port
        "-f null - "                     # decode and discard (headless)
        f"> /tmp/ffmpeg_sta2.log 2>&1 &"
    )

    # small delay to ensure receiver is listening
    time.sleep(1)

    info("*** Starting ffmpeg sender on sta1\n")
    sta1.cmd(
        "ffmpeg "
        "-re "                           # read input at real-time speed
        f"-i {VIDEO_PATH} "
        "-c copy "                       # copy codec, no re-encode
        "-f mpegts "                     # TS over UDP is common
        f"udp://10.0.0.201:{UDP_PORT} "  # sta2 IP + port
        "> /tmp/ffmpeg_sta1.log 2>&1 &"
    )

    info("*** ffmpeg streaming started: sta1 -> sta2\n")

def wait_associated(sta, ifname):
    timeout_s = 5.0
    interval = 0.1
    waited = 0.0

    info(f"*** Waiting for {sta.name} to be associated...\n")
    while waited < timeout_s:
        out = sta.cmd(f"iw dev {ifname} link")
        if "Connected" in out:
            return
        time.sleep(interval)
        waited += interval
    info(f"*** Warning: {sta.name} not associated after {timeout_s}s\n")

def build_and_run_topology():
    setLogLevel('info')
    # Use wmediumd with interference so frames traverse the "air"
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    # Positions help Mininet-WiFi decide associations; keep sniffer near the path
    sta1 = net.addStation('sta1', ip='10.0.0.200/24', position='10,30,0')
    sta2 = net.addStation('sta2', ip='10.0.0.201/24', position='12,30,0')
    ap1  = net.addAccessPoint('ap1', ip='10.0.0.1/24', ssid='ssid-wifi', mode='g', channel='1', position='20,30,0', datapath='user')
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

    # Keep AP IP; not strictly needed for sta1<->sta2, but harmless
    ap1.setIP('10.0.0.1/24', intf='ap1-wlan1')

    # Force sta1 to associate with ap1's SSID
    sta1.cmd('iwconfig sta1-wlan0 essid ssid-wifi')
    wait_associated(sta1, 'sta1-wlan0')

    sta2.cmd('iwconfig sta2-wlan0 essid ssid-wifi')
    wait_associated(sta2, 'sta2-wlan0')

    # --- Disable IPv6 ---
    for node in [sta1, sta2, sn1, ap1]:
        node.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        node.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")

    # OPTIONAL: visualize positions (requires X/GUI). Comment out if headless.
    # net.plotGraph(max_x=100, max_y=100)

    # --- NEW: global hwsim0 sniffer (captures all 802.11 frames) ---
    mon_if = 'hwsim0'
    pcap_path = PCAP_FILE

    info("*** Starting sniffer on hwsim0\n")
    # bring hwsim0 up in the root namespace
    os.system("ifconfig hwsim0 up")
    # NOTE: no -I here; hwsim0 already exposes 802.11 frames
    os.system(
        f'tcpdump -s 0 -i {mon_if} -w {pcap_path} > {TCPDUMP_LOG_FILE} 2>&1 &'
    )
    info(f"*** Sniffer running on {mon_if}; writing to {pcap_path}\n")
    # --------------------------------------------------------------

    info("*** Ready. In another terminal you can stream to sta1/ap1.\n")
    info("*** When done, exit the CLI; we will stop tcpdump automatically.\n")

    # Drop to CLI so you can run your traffic (ffmpeg, ping, etc.)
    CLI(net)

    info("exit command received")

    start_video_stream(sta1, sta2)
    time.sleep(10)

    info("*** Stopping sniffer\n")
    os.system('pkill -f "tcpdump -s 0 -i hwsim0" || true')

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