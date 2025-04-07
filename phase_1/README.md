# Results
The rules currently work as intended, currently the switch is set to blacklist items FROM `h4` and TO `h3`.

Although this is working theoretically and through testing, as PING on `h4` and `h3` isnt working, I still havent gotten PROOF that this is the case
I need to harvest the packet analysis to prove the flow is being disrupted in the intended fashion and that it isnt just broken

So, easiest way i found to get records was to set up XTERM for each host and boot up wireshark on the items im testing:
Tests completed:
| **Test ID** | **Purpose of Test** | **Steps to perform** | **Expected result** | **Actual Result** |
|----|----|----|----|----|
|1.1| Make sure h1 & h2 can communicate with each other | 1. Run ping as h1 to h2 <br>2. Run ping as h2 to h1 | Ping should work as expected on both machines | As expected|
|1.2| Make sure h4 can't send messages but can receive messages | 1. Open wireshark on h4 <br> 2. Open wireshark on designated target <br> 3. Send ping as h4 to target <br> 4. Send ping as target to h4 | Messages sent from h4 should not arrive to target, Messages sent to h4 should be received but target shan't  get replies | As expected |
|1.3| Make sure h3 cant receive messages but can send | Open wireshark on target and h3, send ping as h3 to target and vice versa | Messages from h3 should go through but replies going to h3 shouldnt arrive | As expected |

How were tests performed?
- Ryu
- Mininet