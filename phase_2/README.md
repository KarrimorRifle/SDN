# Phase 2
Contents of phase 2:
- Topology:
  - 4 switch core, layered 1 - 2 - 1, Where each layer can talk to everything 1 layer above / below, each neighbour can talk to each other
  - 4 hosts: 1 host at each end

- SDN:
  - Dynamically path items depending on what links are up and down and depending on what the throughput is

- Learning:
  - Traffic simulation
  - Dynamic ACL adjustments

```mermaid
graph TD
  %% Top Layer
  subgraph Top Layer
    S1[Switch 1]
  end

  %% Middle Layer
  subgraph Middle Layer
    S2[Switch 2]
    S3[Switch 3]
  end

  %% Bottom Layer
  subgraph Bottom Layer
    S4[Switch 4]
  end

  %% Inter-layer connections (each switch connects to all switches in adjacent layers)
  S1 --- S2
  S1 --- S3
  S2 --- S4
  S3 --- S4

  %% Intra-middle layer connection (neighbors can talk)
  S2 --- S3

  %% Hosts:
  H1[Host 1] --- S1
  H4[Host 4] --- S4
```
What will happen: some links will go down, some will go up, but there should almost always be a valid path, if not data shall be uploaded and stored for a bit on the controller, then sent directly to the switch if possible

Need to play around with how the up & down will be handled.

Plan for how the network usually acts:
- The network should be using all switches at max capacity where needed; This means the max throughput overall from h1 - h2 shall be 0.2Mbps
- Where the split isnt required the path will take one route as normal; only when it becomes overloaded shall both switches be used.
- Upon any link failing the SDN shall find a valid path.
- Upon throughput maxing out in the case where a link is up OR down packet loss will be proven inevitable

Items of interest:
- How does a switch tell a link is up or down
- How do we change the ACL based on that
- Does Ryu allow splitting of packets as a default option?
- Packet prioritization
