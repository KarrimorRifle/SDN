# simple_acl.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

class SimpleACL(app_manager.RyuApp):
  OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

  def __init__(self, *args, **kwargs):
    super(SimpleACL, self).__init__(*args, **kwargs)

  # @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
  # def switch_features_handler(self, ev):
  #   datapath = ev.msg.datapath
  #   ofproto = datapath.ofproto
  #   parser = datapath.ofproto_parser

  #   # # Install default rule to send unmatched packets to the controller
  #   # match = parser.OFPMatch()
  #   # actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
  #   #                                   ofproto.OFPCML_NO_BUFFER)]
  #   # self.add_flow(datapath, 0, match, actions)

  #   # Add static ACL rules:
  #   # Example: Block traffic destined for h3 (assume IP 10.0.0.3)
  #   match = parser.OFPMatch(eth_type=0x0800, ipv4_dst='10.0.0.3')
  #   actions = []  # No actions = drop
  #   self.add_flow(datapath, 100, match, actions)

  #   # Block traffic originating from h4 (assume IP 10.0.0.4)
  #   match = parser.OFPMatch(eth_type=0x0800, ipv4_src='10.0.0.4')
  #   actions = []
  #   self.add_flow(datapath, 100, match, actions)


  @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
  def switch_features_handler(self, ev):
    datapath = ev.msg.datapath
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    # First, install the drop rules (high priority)
    # Drop traffic destined for h3 (IP 10.0.0.3)
    match = parser.OFPMatch(eth_type=0x0800, ipv4_dst='10.0.0.3')
    actions = []  # No actions = drop
    self.add_flow(datapath, 100, match, actions)

    # Drop traffic originating from h4 (IP 10.0.0.4)
    match = parser.OFPMatch(eth_type=0x0800, ipv4_src='10.0.0.4')
    actions = []
    self.add_flow(datapath, 100, match, actions)

    # Then install a low-priority default rule that forwards packets normally.
    # The NORMAL action is an OVS extension that causes the switch to use its
    # built-in MAC-learning and switching logic.
    match = parser.OFPMatch()
    actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
    self.add_flow(datapath, 0, match, actions)


  def add_flow(self, datapath, priority, match, actions, buffer_id=None):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser
    inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
    if buffer_id:
      mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id, priority=priority, match=match, instructions=inst)
    else:
      mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
    datapath.send_msg(mod)