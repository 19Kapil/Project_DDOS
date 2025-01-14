#!/usr/bin/env python

"""
This example creates a multi-controller network from semi-scratch by
using the net.add*() API and manually starting the switches and controllers.

This is the "mid-level" API, which is an alternative to the "high-level"
Topo() API which supports parametrized topology classes.

Note that one could also create a custom switch class and pass it into
the Mininet() constructor.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from subprocess import call

def multiControllerNet():
    "Create a network from semi-scratch with multiple controllers."

    info( "*** Creating (reference) controllers\n" )
    c1 = RemoteController('c1', ip='127.0.0.1', port=6653)
    c2 = RemoteController('c2', ip='127.0.0.1', port=6654)
    c3 = RemoteController('c2', ip='127.0.0.1', port=6655)

    net = Mininet(controller=RemoteController, switch=OVSSwitch, waitConnected=True)

    info( "*** Creating hosts and switches\n" )

    # Manually creating switches
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')

    # Manually creating hosts
    hosts1 = [ net.addHost('h3'), net.addHost('h4') ]  # Hosts for switch s1
    hosts2 = [ net.addHost('h5'), net.addHost('h6') ]  # Hosts for switch s2
    hosts3 = [ net.addHost('h7'), net.addHost('h8') ]  # Hosts for switch s3

    info( "*** Creating links\n" )

    # Add links between s1 and its hosts
    for h in hosts1:
        net.addLink(s1, h)

    # Add links between s2 and its hosts
    for h in hosts2:
        net.addLink(s2, h)

    # Add links between s3 and its hosts
    for h in hosts3:
        net.addLink(s3, h)

    # Add links between switches
    net.addLink(s1, s2)
    net.addLink(s2, s3)

    info( "*** Starting network\n" )
    net.build()

    # Start controllers
    c1.start()
    c2.start()

    # Start switches and assign controllers
    s1.start([c1])
    s2.start([c2])

    # For redundancy, s3 can be controlled by both controllers
    s3.start([c3])

    info( "*** Testing network\n" )
    net.pingAll()

    info(" Transfer s1 from c1 to c2")
    call(["ovs-vsctl","setcontroller","s1","tcp:127.0.0.1:6654"])

    

    info( "*** Testing network\n" )
    net.pingAll()

    info( "*** Running CLI\n" )
    CLI(net)

    info( "*** Stopping network\n" )
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')  # for CLI output
    multiControllerNet()
