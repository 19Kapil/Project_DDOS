"""
Create a network where different switches are connected to
different controllers, by creating a custom Switch() subclass.
"""

"""
This example integrates a multi-controller network setup with a custom topology class.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from subprocess import call
import time
import threading

class MyTopo(Topo):
    """Custom topology for multi-controller network."""

    def build(self):
        # Adding switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        s5 = self.addSwitch('s5')
        s6 = self.addSwitch('s6')

        # Adding hosts and connecting to switches
        hosts1 = [self.addHost('h1', cpu=1.0/20, ip="10.0.0.1/24"), self.addHost('h2', cpu=1.0/20, ip="10.0.0.2/24")]
        hosts2 = [self.addHost('h3', cpu=1.0/20, ip="10.0.0.3/24"), self.addHost('h4', cpu=1.0/20, ip="10.0.0.4/24")]
        hosts3 = [self.addHost('h5', cpu=1.0/20, ip="10.0.0.5/24")]
        hosts4 = [self.addHost('h6', cpu=1.0/20, ip="10.0.0.6/24")]
        hosts5 = [self.addHost('h7', cpu=1.0/20, ip="10.0.0.7/24"), self.addHost('h8', cpu=1.0/20, ip="10.0.0.8/24")]
        hosts6 = [self.addHost('h9', cpu=1.0/20, ip="10.0.0.9/24"), self.addHost('h10', cpu=1.0/20, ip="10.0.0.10/24")]
        
        for h in hosts1:
            self.addLink(s1, h)
        for h in hosts2:
            self.addLink(s2, h)
        for h in hosts3:
            self.addLink(s3, h)
        for h in hosts4:
            self.addLink(s4, h)
        for h in hosts5:
            self.addLink(s5, h)
        for h in hosts6:
            self.addLink(s6, h)

        # Adding links between switches
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s4)
        self.addLink(s4, s5)
        self.addLink(s5, s6)

def start_traffic_tests(net):
    """Function to start parallel traffic tests."""
    info("*** Starting automated stress tests\n")
    hosts = [net.get(f'h{i}') for i in range(1, 11)]

    def iperf_test():
        for i in range(len(hosts)//2):
            server, client = hosts[i], hosts[-(i+1)]
            server.cmd("iperf -s -u &")
            client.cmd(f"iperf -c {server.IP()} -u -b 10M -t 60 &")
    
    def file_transfer_test():
        for i in range(len(hosts)//2):
            src, dst = hosts[i], hosts[-(i+1)]
            src.cmd(f"dd if=/dev/zero of=/tmp/testfile bs=1M count=10")
            src.cmd(f"scp /tmp/testfile {dst.IP()}:/tmp/ &")
    
    def stress_cpu():
        for h in hosts[:5]:
            h.cmd("stress-ng --cpu 2 --timeout 60s &")
    
    threading.Thread(target=iperf_test).start()
    threading.Thread(target=file_transfer_test).start()
    threading.Thread(target=stress_cpu).start()

def multiControllerNet():
    """Create a network with the custom topology and multiple controllers."""

    info("*** Creating controllers\n")
    c1 = RemoteController('c1', ip='127.0.0.1', port=6653)
    c2 = RemoteController('c2', ip='127.0.0.1', port=6654)
    c3 = RemoteController('c3', ip='127.0.0.1', port=6655)

    net = Mininet(
        topo=MyTopo(),  # Use the custom topology
        controller=None,  # Manually define controllers
        switch=OVSSwitch,
        waitConnected=True,
    )

    info("*** Adding controllers\n")
    net.addController(c1)
    net.addController(c2)
    net.addController(c3)

    info("*** Starting network\n")
    net.start()

    # Assign controllers to switches
    net.get('s1').start([c1])
    net.get('s2').start([c1])
    net.get('s3').start([c2])
    net.get('s4').start([c2])
    net.get('s5').start([c3])
    net.get('s6').start([c3])

    info("*** Testing network\n")
    net.pingAll()
    
    # Start automated tests
    start_traffic_tests(net)
    
    info("*** Running CLI\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    multiControllerNet()
