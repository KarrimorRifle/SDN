from mininet.topo import Topo

class MyTopo ( Topo ) :
  def build( self ):
    # Add hosts and switches
    leftHost = self.addHost( 'h1' )
    rightHost = self.addHost( 'h2' )
    switch = self.addSwitch( 's3' )

    # Add links
    self.addLink(leftHost, switch)
    self.addLink(rightHost, switch)

    # Add 3rd host that can only send data but not receive anything
    middleHost = self.addHost( 'h3' )
    self.addLink(middleHost, switch)

topos = { 'mytopo': ( lambda: MyTopo() ) }