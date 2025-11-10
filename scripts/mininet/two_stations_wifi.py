from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd, mesh
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

def topology():
    setLogLevel('info')
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1/24')
    sta2 = net.addStation('sta2', ip='10.0.0.2/24')
    ap1  = net.addAccessPoint('ap1', ssid='ssid-wifi', mode='g', channel='1')

    c1 = net.addController('c1')

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info("*** Starting network\n")
    net.build()
    c1.start()
    ap1.start([c1])

    info("*** Ready. Try: sta1 ping -c3 sta2\n")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    topology()
