from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel, info
"""
This topology is for me to get the start of RYU, i will make a basic network consisting of:
  - 4 hosts connected to a switch Each
  - 4 switches are layed out in 1-2-1 where each layer can talk to anyone on the same layer, and can only talk to one above or one below
"""

class MyTopo ( Topo ) :
  def build( self ):
    # Add Hosts
    h1 = self.addHost( 'h1', ip='10.0.0.1/24' )
    h2 = self.addHost( 'h4', ip='10.0.0.2/24' )

    # Add Switches
    s1 = self.addSwitch('s1', dpid="1")
    s2 = self.addSwitch('s2', dpid="2")
    s3 = self.addSwitch('s3', dpid="3")
    s4 = self.addSwitch('s4', dpid="4")

    # Add switch links with bandwidth limits
    # Layer 1 to 2
    self.addLink(s1, s2, bw=0.1)
    self.addLink(s1, s3, bw=0.1)
    # Layer 2
    self.addLink(s2, s3, bw=0.2)
    # Layer 2 to 3
    self.addLink(s2, s4, bw=0.1)
    self.addLink(s3, s4, bw=0.1)

    # Add Switch / Host links
    self.addLink(s1, h1)
    self.addLink(s4, h2)

    # Hosts 2 & 3 should theoretically be able to have 750Kbps throughput
    # H1 & h4 should only be able to handle 500Kbps throughput total


topos = { 'mytopo': ( lambda: MyTopo() ) }

if __name__ == '__main__':
  setLogLevel('info')
  topo = MyTopo()
  net = Mininet(topo=topo, switch=OVSSwitch, controller=None)

  c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
  net.start()
  net.pingAll()
  net.stop()