# LX200GPS Telescope Simulator
This is a suite of python3 programs to simulate the behaviour of an LX200GPS telescope using its serial command protocol.  They were written with extensive input from openAI(chatgpt).
It can be used with the indi_lx200gps driver in Ekos or P.I.N.S.instead of the real telescope.  
It is intended to watch the commands that are sent to the real telescope by astronomy software  
such as KStars/Ekos or P.I.N.S./Touch-n-Stars, with which the simulator was tested. It might also work  
with other programs that send commands to an LX200GPS telescope via a serial interface.

The simulator can either run on the same machine where the astronomy software is running  
(indi or P.I.N.S. with indi) or on a different machine. A TCP to Serial bridge (tcp_server.py)  
either connects to the simulator via 127.0.0.1 (locahost) when running the simulator on the same machine or to the IP address of the separate (server) machine running the simulator.

## Usage running simulator on the same machine as indi/P.I.N.S.
(Optional: create a python virtual environment and activate it).


Open a terminal on the P.I.N.S./indi machine and clone the repository
```
cd ~
git clone https://github.com/airborneastro/LX200GPS.git
cd LX200GPS
```
and then start the simulator with
```
./start_sim.py
```
The simulator will expose a serial client port as a virtual serial device. Default:
```
/tmp/lx200client
```
to which you connect the LX200GPS mount of P.I.N.S./indi or Ekos/indi.  
In P.I.N.S. you need to use the "Manual Port" mode of providing the serial device port.
In Ekos, use the "Devices Port Selector".

With 
```
./start_sim.py --clientport mytelescope
```
the serial port to connect to would be
```
/tmp/mytelescope
```
After connecting the telescope device in PINS or Ekos, the simulator will echo all commmands sent to the telescope simulator and print the simulator telescope responses. After the startup commands are processed, try to slew the telescope to a target with KStars/Ekos or Stellarium within Touch-n-Stars

After disconnecting the mount device in Ekos or PINS, there is a timeout of 60 seconds before the simulator is restarted automatically. You cannot reconnect before that timeout is finished.

After disconnect, you can terminate the simulator with Ctrl-C in the terminal.

## Usage running the simulator on a separate machine
Clone the repository on both the indi/PINS machine as well as the separate simulator machine.  
(on the indi/PINS machine you would only need sim_start.py and tcp_server.py)
On both machines:
```
cd ~/LX200GPS
```
On the simulator machine, start the simulator in a terminal with:
```
./lx200gps_sim.py
```
On the indi/PINS machine, start the TCP-to-serial connection with:
```
./start_sim.py --server XXX.XXX.XXX.XXX
```
with XXX.XXX.XXX.XXX the IP address of the machine running the simulator. Naturally, the simulator machine must be reachable within the network that the PINS/indi machine is in.

After that, proceed as above. The same 60 second timeout applies. Do not forget to terminate the simulator and the TCP-connection with Ctrl-C on both machines.

## Park/Unpark behaviour
The LX200GPS indi driver only knows a "Park" command and no "Unpark" command. After parking, the telescope is expected to be powered off (that is what its handbox says), and there is obviously no further response from the telescope. To simulate that, you should disconnect the Ekos/PINS mount and wait for the simulator timeout restart before reconnecting. After reconnecting, issue "Unpark" in Ekos or PINS/Touch-n-Stars.

The park position is fixed in the simulator to HA = 0, DEC = 0, so at the meridian and the celestial equator. (The simulator knows the local sidereal time).

The present simulator however handles the unpark procedure also without disconnect/reconnect by sending the (simulated) :I# command to the telescope, waking it up from park without power toggle (or disconnect). This is not implemented in the standard indi_lx200gps driver (which is a symlink to indi_lx200generic). There is a companion repository (fork of indilib) on my github which has a modification to the source code of lx200gps.cpp (and more) which processes the :I command, rebooting a parked LX200GPS without power toggle and also implements the :hIyymmddhhmmss initialization command. This is useful for a permanently mounted LX200GPS with its GPS switched off. On power-up (or after the :I reboot) the handbox waits at the "DAYLIGHT SAVING YES/NO" prompt, which is then answered by the :hIyymmddhhmmss initialization command.
