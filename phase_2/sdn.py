from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3, ether
from ryu.lib.packet import packet, ethernet, lldp
from typing import Dict
from dataclasses import dataclass
from ryu.lib import hub
from collections import deque, defaultdict

"""
# Handler for packet-in events: process the incoming packet.
@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
def _packet_in_handler(self, ev):

# Handler for when a switch connects; installs the table-miss rule.
@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
def switch_features_handler(self, ev):
"""

"""
TODO
Review current script plan and make sure it:
Done - Handles LLDP packets
Done - Creates Spanning Tree for broadcasts
Done - Allow broadcasting
Done, but need fixing - Adjusts ACLs as soon as we get any packet from any kind of host
  Fixes:
  - Port blocking sometimes blocks all three ports, GPT is assessing the the predecessor wasnt being accounted for, or which port it traveled through
  - Race conditions, the writing of ACLs, in create_paths_to_host seems to work, but it seems to break after a few pings, make this handle race conditions
  - Need to
- sort load balancing to maximise throughput
- Handle edges / switches failing
"""

@dataclass
class HostPos:
   dpid: int
   dpid_port: int

class SimpleSwitch(app_manager.RyuApp):
  # Specify the OpenFlow version; here we use 1.3.
  OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

  def __init__(self, *args, **kwargs):
    super(SimpleSwitch, self).__init__(*args, **kwargs)
    # Create a dictionary to map switch datapath id to learned MAC-port mappings.
    self.mac_to_port = {}
    # Create a dictionary to map DPID to DPID:
    """
      DICT
      [
        dpid, 
        DICT
        [
          port,
          dpid
        ]
      ]
    """
    self.DPID_to_port: Dict[int, Dict[int, int]] = {}
    # Create a dictionary of which ports to block on which DPID for BROADCASTS
    self.DPID_block_port = {}
    # Store the datapaths
    self.datapaths = {}
    self.host_to_dpid: Dict[str, HostPos] = {}
    self.expected_switches = 4
    # Mac locks
    self._mac_in_progress = set()
    self._map_lock = hub.Semaphore()

  # Config dispatch handler
  @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
  def switch_features_handler(self, ev: ofp_event.EventOFPSwitchFeatures) -> None:
    msg = ev.msg # has .body
    datapath = msg.datapath
    dpid = datapath.id

    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto

    self.logger.info("Switch %s connected", dpid)

    # Add network device
    self.datapaths[dpid] = datapath
    if dpid not in self.DPID_to_port:
      self.DPID_to_port[dpid] = {}
      self.DPID_block_port[dpid] = []

    # Add LLDP handling rule (send back to controller)
    match_lldp = parser.OFPMatch(eth_type=0x88CC)
    actions_lldp = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                      ofproto.OFPCML_NO_BUFFER)]
    self.add_flow(datapath, priority=100, match=match_lldp, actions=actions_lldp)

    # Add ARP broadcast propogation: Also send it to the controller
    match_broadcast = parser.OFPMatch(eth_dst='ff:ff:ff:ff:ff:ff', eth_type=0x0806)
    actions_broadcast = [
                          parser.OFPActionOutput(ofproto.OFPP_FLOOD, 0),
                          parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                            ofproto.OFPCML_NO_BUFFER)
                        ]
    self.add_flow(datapath, 10, match_broadcast, actions_broadcast)

    # # Add table miss rule
    match = parser.OFPMatch()
    actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                      ofproto.OFPCML_NO_BUFFER)]
    self.add_flow(datapath, 0, match, actions)

    if len(self.datapaths.keys()) == self.expected_switches:
      for datapath in self.datapaths.values():
        # Ask for port description
        req = parser.OFPPortDescStatsRequest(datapath)
        datapath.send_msg(req)

  # Port description handler
  @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
  def port_desc_stats_reply_handler(self, ev):
    datapath = ev.msg.datapath
    chassis_id = str(datapath.id)
    ofproto = datapath.ofproto
    for p in ev.msg.body:
      if not (p.state & ofproto.OFPPS_LINK_DOWN):
        port_no = p.port_no
        port_id = str(port_no)
        self.send_lldp_packet(datapath=datapath, port=port_no, chassis_id=chassis_id, port_id=port_id)

  # Switch packet handler
  @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
  def _packet_in_handler(self, ev):
    # If LLDP packet check the port it came from and add to self.DPID_to_port
    msg = ev.msg
    datapath = msg.datapath
    in_port = msg.match['in_port']
    pkt = packet.Packet(msg.data)

    eth_pkt = pkt.get_protocol(ethernet.ethernet)
    if eth_pkt is None:
      return  # Not an Ethernet packet

    if eth_pkt.ethertype == 0x88cc:
      self.logger.info("LLDP packet received on port %s", in_port)

      # Parse the LLDP protocol from the packet:
      lldp_pkt = pkt.get_protocol(lldp.lldp)
      if lldp_pkt is None:
          return
      
      neighbor_dpid = None
      for tlv in lldp_pkt.tlvs:
          if isinstance(tlv, lldp.ChassisID):
              # This should be the chassis_id you set when sending the LLDP packet.
              # In your sending function, you probably set:
              # chassis_id = str(datapath.id)
              if isinstance(tlv.chassis_id, bytes):
                  neighbor_dpid_str = tlv.chassis_id.decode('utf-8')
              else:
                  neighbor_dpid_str = str(tlv.chassis_id)
              try:
                  neighbor_dpid = int(neighbor_dpid_str)
              except ValueError:
                  self.logger.error("Invalid chassis ID: %s", neighbor_dpid_str)
              break

      if neighbor_dpid is not None:
          # Store the mapping: for the local switch (datapath.id) at in_port,
          # the neighbor switch's DPID is neighbor_dpid.
          if datapath.id not in self.DPID_to_port:
              self.DPID_to_port[datapath.id] = {}
          self.DPID_to_port[datapath.id][in_port] = neighbor_dpid
          self.logger.info("Port %s on switch %s connects to neighbor switch %s",
                            in_port, datapath.id, neighbor_dpid)
          
          # We have added a new connection so we should check for loops
          self.handle_broadcast_loops()
      return

    if eth_pkt.ethertype == 0x0806:
      self.logger.info("%s: ARP packet:\n  port: %s\n  to: %s\n  from:%s", datapath.id, in_port, eth_pkt.src, eth_pkt.dst)
      # Grab the sender's MAC address
      src_mac = eth_pkt.src
      # Add to the Mac addresses:
      if src_mac not in self.host_to_dpid:
        # Add where it came from
        self.host_to_dpid[src_mac] = HostPos(dpid=None, dpid_port=None)
        # print("Logging host")
      if self.host_to_dpid[src_mac].dpid != None or self.host_to_dpid[src_mac].dpid != int(datapath.id):
        with self._map_lock:
            if src_mac in self._mac_in_progress:
              return
            self._mac_in_progress.add(src_mac)
            print("Handling host")
        try:
          self.host_to_dpid[src_mac].dpid = datapath.id
          self.host_to_dpid[src_mac].dpid_port = in_port
          self.create_paths_to_host(src_mac)
        finally:
          hub.spawn_after(5, self._mac_in_progress.discard, src_mac)

  # Utility function to add paths to a host
  def create_paths_to_host(self, src_mac, dpid=None, prev_dpid=None, traversed=None):
    if dpid == None:
      dpid = self.host_to_dpid[src_mac].dpid
      traversed = [dpid]
    
    datapath = self.datapaths[dpid]
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto

    match = None
    action = None

    ports_dict = self.DPID_to_port.get(dpid, {})

    # Add ACL
    if prev_dpid == None:
      port = self.host_to_dpid[src_mac].dpid_port
      match = parser.OFPMatch(eth_dst=src_mac)
      action = [parser.OFPActionOutput(port)]
    else:
      port = None
      for port_, nbr in ports_dict.items():
        if nbr == prev_dpid:
          port = port_
      match = parser.OFPMatch(eth_dst=src_mac)
      action = [parser.OFPActionOutput(port)]
    
    self.add_flow(datapath, priority=100, match=match, actions=action)

    # Traverse BFS calling function
    to_traverse = []
    for port, nbr in ports_dict.items():
      if nbr not in traversed:
        traversed.append(nbr)
        to_traverse.append(nbr)
    for item in to_traverse:
      self.create_paths_to_host(src_mac, item, dpid, traversed)

    

  # Utility function to add flows to a switch.
  def add_flow(self, datapath, priority, match, actions, buffer_id=None):
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto

    # Define the instruction with the action list.
    inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
    # Build the flow mod message.
    if buffer_id:
        mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                priority=priority, match=match,
                                instructions=inst)
    else:
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
    datapath.send_msg(mod)

  # Utility to add blockers to turn switch graph into a MST
  """
  Issues:
  - How do we recognise a loop?
      Utilise a DFS, if DPID reoccurs 
      when traveling there is a loop
  - How do we make sure we remove a loop to allow broadcasting to be most efficient?
      For broadcasting, since the weights dont really matter,
      we should just do BFS to ensure broadcasting efficiency
  """
  def handle_broadcast_loops(self):
    """Build a loop‑free spanning tree and install drop‑flows on
    redundant links.  Guarantees **at least one** forwarding port per switch.
    This is a true breadth‑first search that touches each switch once.
    """
    if not self.DPID_to_port:
      return  # nothing to do

    # (Re)initialise state for this traversal
    self.DPID_block_port = defaultdict(set)
    root = next(iter(self.DPID_to_port))       # pick the first switch seen

    visited   = {root}
    queue     = deque([root])                  # BFS frontier
    link_seen = set()                          # frozenset({a, b}) tracks cables

    while queue:
      dpid = queue.popleft()

      # Skip switches that disappeared mid‑traversal
      if dpid not in self.DPID_to_port:
        continue

      for port, nbr in self.DPID_to_port[dpid].items():
        # Ignore ports we’ve already blocked in an earlier run
        if port in self.DPID_block_port[dpid]:
          continue

        # Treat parallel links as duplicates
        link_id = frozenset((dpid, nbr))
        if link_id in link_seen:
          self._maybe_block_port(dpid, port)
          continue
        link_seen.add(link_id)

        # Cross‑edge → would form a cycle → block current port
        if nbr in visited:
          self._maybe_block_port(dpid, port)
          continue

        # First time we see this neighbour → keep the port & explore later
        visited.add(nbr)
        queue.append(nbr)

    self.logger.info("Broadcast‑loop protection done; blocked ports: %s",
                     dict(self.DPID_block_port))


  def _maybe_block_port(self, dpid, port):
    """Install a drop‑flow for ff:ff:ff:ff:ff:ff on (dpid, port) unless doing
    so would isolate the switch (i.e. leave zero forwarding interfaces)."""
    # How many ports would remain forwarding if we blocked this one?
    total_ports     = len(self.DPID_to_port.get(dpid, {}))
    already_blocked = len(self.DPID_block_port[dpid])
    if total_ports - already_blocked <= 1:
      # Would isolate the switch – keep at least one uplink alive
      return

    datapath = self.datapaths[dpid]
    parser   = datapath.ofproto_parser
    match    = parser.OFPMatch(in_port=port, eth_dst='FF:FF:FF:FF:FF:FF')
    self.add_flow(datapath, 110, match, [])        # drop broadcast on this port

    self.DPID_block_port[dpid].add(port)
    self.logger.debug("Blocked broadcast on DPID %s port %s", dpid, port)
     

  """LLDP packet
  Preamble:         8 B
  Destination MAC:  6 B
  Source MAC:       6 B
  EtherTyper:       2 B
  Payload:          ? B
  CRC:              4 B
  """

  """LLDP Packet Payload
  Minimum of 3 TLVs
  where TLV Structure is:
  - Type:   7 b
  - Length: 9 b
  - Value:  0-507 B
  """
  # Utility function to send LLDP packet to every Port
  def send_lldp_packet(self, datapath, port, chassis_id, port_id):
    # Build an LLDP packet
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto
    
    # Create LLDP TLVs for chassis ID, port ID, and TTL
    chassis_tlv = lldp.ChassisID(subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED, chassis_id=str(chassis_id).encode('utf-8'))
    port_tlv = lldp.PortID(subtype=lldp.PortID.SUB_LOCALLY_ASSIGNED, port_id=str(port_id).encode('utf-8'))
    ttl_tlv = lldp.TTL(ttl=120)  # Typical TTL in seconds
    lldp_pkt = lldp.lldp(tlvs=[chassis_tlv, port_tlv, ttl_tlv])
    
    # Create Ethernet header with LLDP multicast destination
    eth_pkt = ethernet.ethernet(dst='01:80:C2:00:00:0E',
                                src='00:00:00:00:00:01',  # Replace with appropriate source MAC
                                ethertype=ether.ETH_TYPE_LLDP)
                                
    pkt = packet.Packet()
    pkt.add_protocol(eth_pkt)
    pkt.add_protocol(lldp_pkt)
    pkt.serialize()
    
    actions = [parser.OFPActionOutput(port)]
    out = parser.OFPPacketOut(datapath=datapath,
                              buffer_id=ofproto.OFP_NO_BUFFER,
                              in_port=ofproto.OFPP_CONTROLLER,
                              actions=actions,
                              data=pkt.data)
    datapath.send_msg(out)
