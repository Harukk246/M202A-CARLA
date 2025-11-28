import glob
import os
import subprocess
import time
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TCPDUMP_LOG_FILE = os.path.join(PROJECT_ROOT, 'tcpdump.log')
PCAP_DIR = os.path.join(PROJECT_ROOT, 'pcaps')
VIDEO_DIR = "/home/wifi/videos"
MONITOR_INTERFACE = "hwsim0"

UDP_PORT = 5000

def start_ffmpeg_receiver(sta2, log_path):
    sta2.cmd("pkill -f 'ffmpeg .*udp://0.0.0.0' || true")
    info("*** Starting ffmpeg receiver on sta2\n")
    sta2.cmd(
        "nohup ffmpeg "
        "-loglevel error "
        f"-i udp://0.0.0.0:{UDP_PORT} "
        "-f null - "
        f"> {log_path} 2>&1 &"
    )


def stop_ffmpeg_receiver(sta2):
    sta2.cmd("pkill -f 'ffmpeg .*udp://0.0.0.0' || true")


def get_video_files():
    video_files = sorted(glob.glob(os.path.join(VIDEO_DIR, "*.mp4")))
    if not video_files:
        info(f"*** No .mp4 files found in {VIDEO_DIR}\n")
    return video_files


def start_tcpdump_capture(pcap_path):
    os.makedirs(os.path.dirname(pcap_path), exist_ok=True)
    os.system(f"ifconfig {MONITOR_INTERFACE} up")
    info(f"*** Starting tcpdump capture to {pcap_path}\n")
    log_handle = open(TCPDUMP_LOG_FILE, "a")
    proc = subprocess.Popen(
        [
            "tcpdump",
            "-s", "0",
            "-i", MONITOR_INTERFACE,
            "-w", pcap_path,
        ],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    # give tcpdump a moment to initialize
    time.sleep(0.5)
    return proc, log_handle


def stop_tcpdump_capture(proc, log_handle):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    log_handle.close()


def stream_single_video(sta1, sta2, video_path):
    basename = os.path.splitext(os.path.basename(video_path))[0]
    pcap_path = os.path.join(PCAP_DIR, f"{basename}.pcap")
    receiver_log = f"/tmp/ffmpeg_sta2_{basename}.log"
    sender_log = f"/tmp/ffmpeg_sta1_{basename}.log"

    tcpdump_proc, tcpdump_log = start_tcpdump_capture(pcap_path)
    start_ffmpeg_receiver(sta2, receiver_log)
    time.sleep(1)

    info(f"*** Streaming {video_path} -> {pcap_path}\n")
    sta1.cmd(
        "ffmpeg "
        "-re "
        f"-i {video_path} "
        "-c copy "
        "-f mpegts "
        f"udp://10.0.0.201:{UDP_PORT} "
        f"> {sender_log} 2>&1"
    )

    stop_ffmpeg_receiver(sta2)
    stop_tcpdump_capture(tcpdump_proc, tcpdump_log)
    info(f"*** Completed {video_path}\n")


def stream_all_videos(sta1, sta2):
    video_files = get_video_files()
    if not video_files:
        return

    info(f"*** Streaming {len(video_files)} video(s) sequentially\n")
    for video_path in video_files:
        stream_single_video(sta1, sta2, video_path)


def cleanup_previous_outputs():
    try:
        os.remove(TCPDUMP_LOG_FILE)
    except FileNotFoundError:
        pass

    if os.path.isdir(PCAP_DIR):
        for filename in os.listdir(PCAP_DIR):
            if filename.endswith(".pcap"):
                os.remove(os.path.join(PCAP_DIR, filename))

def wait_associated(sta, ifname):
    timeout_s = 10.0
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
    wifi_passwd = '123456780'
    sta1 = net.addStation(
        'sta1',
        ip='10.0.0.200/24',
        position='10,30,0',
        ssid='ssid-wifi',
        passwd=wifi_passwd,
        encrypt='wpa2',
    )
    sta2 = net.addStation(
        'sta2',
        ip='10.0.0.201/24',
        position='12,30,0',
        ssid='ssid-wifi',
        passwd=wifi_passwd,
        encrypt='wpa2',
    )
    ap1 = net.addAccessPoint(
        'ap1',
        ip='10.0.0.1/24',
        ssid='ssid-wifi',
        mode='g',
        channel='1',
        position='20,30,0',
        datapath='user',
        passwd=wifi_passwd,
        encrypt='wpa2',
    )

    info("*** Configuring wifi nodes\n")
    # Optional propagation model (helps emulate distance/attenuation)
    net.setPropagationModel(model="logDistance", exp=4)
    net.configureWifiNodes()

    info("*** Starting network\n")
    net.build()
    net.start()

    # Keep AP IP; not strictly needed for sta1<->sta2, but harmless
    ap1.setIP('10.0.0.1/24', intf='ap1-wlan1')

    # Force sta1 to associate with ap1's SSID
    # sta1.cmd('iwconfig sta1-wlan0 essid ssid-wifi')
    wait_associated(sta1, 'sta1-wlan0')

    # sta2.cmd('iwconfig sta2-wlan0 essid ssid-wifi')
    wait_associated(sta2, 'sta2-wlan0')

    # --- Disable IPv6 ---
    for node in [sta1, sta2, ap1]:
        node.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        node.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")

    # OPTIONAL: visualize positions (requires X/GUI). Comment out if headless.
    # net.plotGraph(max_x=100, max_y=100)

    CLI(net)

    info("*** Starting sequential streaming workload\n")
    stream_all_videos(sta1, sta2)

    info("*** Streaming complete.\n")

    info("exit command received")

    info("*** Stopping network\n")
    net.stop()

if __name__ == "__main__":
    cleanup_previous_outputs()
    build_and_run_topology()

    if os.path.exists(TCPDUMP_LOG_FILE):
        with open(TCPDUMP_LOG_FILE) as f:
            print(f.read())
    else:
        info(f"*** No tcpdump log found at {TCPDUMP_LOG_FILE}\n")

    print("\nDone!")
