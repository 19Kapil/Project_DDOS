"""
Network Topology to run an environment to perform generate normal traffic in multicontroller SDN network environment
"""



from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from subprocess import call

from time import sleep 
import os

from datetime import datetime 
from random import randrange, choice

class MyTopo(Topo):
    "Custom topology for multi-controller network."

    def build(self):
        # Adding switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        s5 = self.addSwitch('s5')
        s6 = self.addSwitch('s6')


        # Adding hosts and connecting to switches
        hosts1 = [self.addHost('h1',cpu = 1.0/20,ip="10.0.0.1/24"), self.addHost('h2',cpu = 1.0/20,ip="10.0.0.2/24")]
        hosts2 = [self.addHost('h3',cpu = 1.0/20,ip="10.0.0.3/24"), self.addHost('h4',cpu = 1.0/20,ip="10.0.0.4/24")]
        hosts3 = [self.addHost('h5',cpu = 1.0/20,ip="10.0.0.5/24")]
        hosts4 = [self.addHost('h6',cpu = 1.0/20,ip="10.0.0.6/24")]
        hosts5 = [self.addHost('h7',cpu = 1.0/20,ip="10.0.0.7/24"), self.addHost('h8',cpu = 1.0/20,ip="10.0.0.8/24")]
        hosts6 = [self.addHost('h9',cpu = 1.0/20,ip="10.0.0.9/24"), self.addHost('h10',cpu = 1.0/20,ip="10.0.0.10/24")]
        

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

def ip_generator():
    ip = ".".join(["10","0","0",str(randrange(1,11))])
    return ip

def multiControllerNet():
    "Create a network with the custom topology and multiple controllers."

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

    
    h1 = net.get('h1')
    h2 = net.get('h2')
    h3 = net.get('h3')
    h4 = net.get('h4')
    h5 = net.get('h5')
    h6 = net.get('h6')
    h7 = net.get('h7')
    h8 = net.get('h8')
    h9 = net.get('h9')
    h10 = net.get('h10')

    hosts = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10]

    info("\n-----------------------------------------------------")
    info("\nGenerating DDOS Traffic")

    # Check and Create web server dir 
    webserver_dir = '/home/mininet/webserver'
    if not os.path.exists(webserver_dir):
        h1.cmd(f'mkdir -p {webserver_dir}')

    #HTTP server
    h1.cmd('cd /home/mininet/webserver')
    h1.cmd('python -m SimpleHTTPServer 80 &')


    #iperf server TCP and UDP
    h1.cmd('iperf -s -p 5050 &') 

    h1.cmd('iperf -s -u -p 5051 &')

    sleep(2)

    for h in hosts:
        h.cmd('cd /home/mininet/webserver')
    
 
    # Simulating attack scenarios
    src = choice(hosts)
    dst = ip_generator()   
    info("\n--------------------------------------------------------------------------------\n"
        "Performing ICMP (Ping) Flood\n"
        "--------------------------------------------------------------------------------\n")
    src.cmd(f"timeout 5s hping3 -1 -V -d 120 -w 64 -p 80 --flood {dst}")
    sleep(50)
            
    # src = choice(hosts)
    # dst = ip_generator()   
    # info("\n--------------------------------------------------------------------------------\n"
    #     "Performing UDP Flood\n"
    #     "--------------------------------------------------------------------------------\n")
    # src.cmd(f"timeout 5s hping3 -2 -V -d 120 -w 64 --flood {dst}")
    # sleep(100)
        
    # src = choice(hosts)
    # dst = ip_generator()    
    # info("\n--------------------------------------------------------------------------------\n"
    #     "Performing TCP-SYN Flood\n"
    #     "--------------------------------------------------------------------------------\n")
    # src.cmd('timeout 5s hping3 -S -V -d 120 -w 64 -p 80 --flood 10.0.0.1')
    # sleep(100)
        
    # src = choice(hosts)
    # dst = ip_generator()   
    # info("\n--------------------------------------------------------------------------------\n"
    #     "Performing LAND Attack\n"
    #     "--------------------------------------------------------------------------------\n")
    # src.cmd(f"timeout 5s hping3 -1 -V -d 120 -w 64 --flood -a {dst} {dst}")
    # sleep(100)

    info("\n--------------------------------------------------------------------------------\n"
        "Attack simulation completed\n"
        "--------------------------------------------------------------------------------\n")

        
    info("\n----------------------------------------------------------------------------")

    info("\n*** Running CLI\n")
    CLI(net)

    info("\n*** Stopping network\n")
    net.stop()


if __name__ == "__main__":
    start = datetime.now()
    setLogLevel("info")
    multiControllerNet()
    end = datetime.now()
    print(end-start)
