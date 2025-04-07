from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel, info
"""
This topology is for me to get the start of RYU, i will make a basic network consisting of:
  - 4 hosts connected to one switch
  - 1 of the hosts will be `receive only`
  - Another host will be `send only`
"""

class MyTopo ( Topo ) :
  def build( self ):
    # Add hosts and switches
    host1 = self.addHost( 'h1', ip='10.0.0.1/24' )
    host2 = self.addHost( 'h2', ip='10.0.0.2/24' )
    host3 = self.addHost( 'h3', ip='10.0.0.3/24' )  # Can send only
    host4 = self.addHost( 'h4', ip='10.0.0.4/24' )  # Can receive only

    switch = self.addSwitch( 's1' )

    # Add links
    self.addLink(host1, switch)
    self.addLink(host2, switch)
    self.addLink(host3, switch)
    self.addLink(host4, switch)

topos = { 'mytopo': ( lambda: MyTopo() ) }

if __name__ == '__main__':
  setLogLevel('info')
  topo = MyTopo()
  net = Mininet(topo=topo, switch=OVSSwitch, controller=None)

  c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
  net.start()
  net.pingAll()
  net.stop()