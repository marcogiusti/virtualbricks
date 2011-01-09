#!/usr/bin/python

import sys
import os
import ConfigParser
import time
import re
import subprocess 
import gobject
import signal
import string
import random
import threading
import virtualbricks_GUI
import virtualbricks_Global as Global
import select

class InvalidNameException(Exception):
	def __init__(self):
		pass
class BadConfigException(Exception):
	def __init__(self):
		pass
class NotConnectedException(Exception):
	def __init__(self):
		pass
class LinkdownException(Exception):
	def __init__(self):
		pass



class Plug():
	def __init__(self, _brick):
		self.brick = _brick
		self.sock=None
		self.antiloop=False

	def configured(self):
		if self.sock is None:
			return False
		else:
			return True

	def connected(self):
		if self.antiloop:
			print "Network loop detected!"
			self.antiloop = False
			return False

		self.antiloop = True
		if self.sock is None or self.sock.brick is None:
			self.antiloop=False
			return False
		self.sock.brick.poweron()
		if self.sock.brick.proc is None:
			self.antiloop = False
			return False
		for p in self.sock.brick.plugs:
			if p.connected() == False:
				self.antiloop = False
				return False
		self.antiloop = False
		print "connect ok"
		return True
		
	def connect(self, _sock):
		if _sock == None:
			return False
		else:
			_sock.plugs.append(self)
			self.sock = _sock
			return True
	def disconnect(self):
		self.sock=""
		

class Sock():
	def __init__(self, _brick, _nickname):
		self.brick = _brick
		self.nickname=_nickname
		self.path = ""
		self.plugs = []
		self.brick.factory.socks.append(self)

	def get_free_ports(self):
		return int(self.brick.cfg.numports) - len(self.plugs)
	
	def has_valid_path(self):
		return os.access(os.path.dirname(self.path), os.W_OK)
		
		

class BrickConfig():
	def set(self,attr):
		kv = attr.split("=")
		if len(kv) != 2:
			return False
		else:
			print "setting %s to '%s'" % (kv[0], kv[1])
			# pure magic. I love python.
			self.__dict__[kv[0]] = kv[1]
		

	def get(self, key):
		try:
			val = self.__dict__[key]
		except KeyError:
			return None
		return self.__dict__[key]

	def dump(self):
		for (k,v) in self.__dict__.items():
			print "%s=%s" % (k,v)



class Brick():
	def __init__(self, _factory, _name):
		self.factory = _factory
		self.name = _name
		self.plugs = []
		self.socks = []
		self.proc = None
		self.cfg = BrickConfig()
		self.cfg.numports = 0
		self.command_builder=dict()
		self.factory.bricks.append(self)
		self.gui_changed = False
		self.need_restart_to_apply_changes = False
		self.needsudo = False
		
	def cmdline(self):
		return ""

	def on_config_changed(self):
		return
	
	def help(self):
		print "Object type: " + self.get_type()
		print "Possible configuration parameter: "
		for (k,v) in self.command_builder.items():
			if not k.startswith("*"):
				print v,
				print "  ",
				print "\t(like %s %s)" % (self.prog(), k)	
			else:
				print k + " " + v + "\tset '" + v + "' to append this value to the command line with no argument prefix"
		print "END of help"
		print

	def configured(self):
		return False
	
	def properly_connected(self):
		for p in self.plugs:
			if p.configured() == False:
				return False
		return True
	
	def check_links(self):
		for p in self.plugs:
			if p.connected() == False:
				return False
		return True
	

	def configure(self, attrlist):
		for attr in attrlist:
			self.cfg.set(attr)
		self.on_config_changed()
	
	def connect(self,endpoint):
		for p in self.plugs:
			if not p.configured():
				if (p.connect(endpoint)):
					self.on_config_changed()
					self.gui_changed = True
					return True
		return False
				
	def disconnect(self):
		for p in self.plugs:
			if p.configured():
				p.disconnect()
		self.on_config_changed()
		



	############################
	########### Poweron/Poweroff
	############################

	def poweron(self):

		if not self.configured():
			print "bad config"
			raise BadConfigException
		if not self.properly_connected():
			print "not connected"
			raise NotConnectedException
		if not self.check_links():
			print "link down"
			raise LinkdownException
		self._poweron()

	def build_cmd_line(self):
		res = []
		for (k,v) in self.command_builder.items():
			if not k.startswith("#"):
				value = self.cfg.get(v)
				if value is "*":
					res.append(k)
				elif value is not None and len(value) > 0:
					if not k.startswith("*"):
						res.append(k)
					res.append(value)
		return res


	def args(self):
		res = []
		if self.needsudo:
			res.append('gksu')
		res.append(self.prog())
		for c in self.build_cmd_line():
			res.append(c)
		return res
	
	def _poweron(self):
		if (self.proc != None):
			return
		command_line = self.args()
		print 'Starting [%s]' % (command_line)
		self.proc = subprocess.Popen(command_line, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#		self.proc.fromchild.close()
#		self.proc.tochild.close()
		self.pid = self.proc.pid
		self.post_poweron()
		
	def poweroff(self):
		print "Shutting down %s" % self.name
		if (self.proc == None):
			return False
		try:
			os.kill(self.proc.pid, 15)
		except:
			pass
		self.proc.wait()
		self.proc = None
		self.need_restart_to_apply_changes = False
		self.post_poweroff()

	def post_poweron(self):
		pass
	def post_poweroff(self):
		pass


	#############################
	# Console related operations.
	#############################
	def has_console(self):
		if (self.cfg_mgmt != None) and self.proc != None:
			return True
		else:
			return False

	def open_console(self):
		if not self.has_console():
			return 
		else:
			cmdline = ['xterm', '-T',self.name,'-e','vdeterm',self.cfg_mgmt]
			console = subprocess.Popen(cmdline)

	def send(self,msg):
		if self.proc == None:
			return
		self.proc.stdin.write(msg)

	def recv(self):
		if self.proc == None:
			return ''
		return self.proc.stdout.read()

	def close_tty(self):
		sys.stdin.close()
		sys.stdout.close()
		sys.stderr.close()
		

class Switch(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.active = 0
		self.cfg.path = Global.MYPATH + '/' + self.name + '.ctl' 
		self.cfg.console = Global.MYPATH + '/' + self.name + '.mgmt' 
		self.cfg.numports = "32"
		self.cfg.hub = ""
		self.cfg.fstp = ""
		self.ports_used = 0
		self.command_builder = {"-s":'path',
					"-M":'console',
					"-x":"hubmode", 
					"-n":"numports", 
					"-F":"fstp", 
					"--macaddr":"macaddr",
					"-m":"mode",
					"-g":"group",
					"--priority":"priority",
					"--mgmtmode":"mgmtmode",
					"--mgmtgroup":"mgmtgroup"
					
					}
		portname = self.name + "_port"
		self.socks.append(Sock(self, portname))
		self.on_config_changed()
	

	def prog(self):
		return Global.VDEPATH + "/vde_switch"

	def get_type(self):
		return 'Switch'

	def on_config_changed(self):
		self.socks[0].path=self.cfg.path
		self.socks[0].ports=int(self.cfg.numports)

		if (self.proc is not None):
			self.need_restart_to_apply_changes = True
	
	def configured(self):
		return self.socks[0].has_valid_path()

class Tap(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.active = 0
		self.cfg.name = _name
		self.command_builder = {"-s":'sock', "*tap":"name"}
		self.cfg.sock = ""
		self.plugs.append(Plug(self))
		#self.needsudo = True
	

	def prog(self):
		return Global.VDEPATH + "/vde_plug2tap"

	def get_type(self):
		return 'Tap'

	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock = self.plugs[0].sock.path
		if (self.proc is not None):
			self.need_restart_to_apply_changes = True

	def configured(self):
		return (self.plugs[0].sock is not None)	


class Wire(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.active = 0
		self.cfg.name = _name
		self.command_builder = {"#sock left":"sock0", "#sock right":"sock1"}
		self.cfg.sock0 = ""
		self.cfg.sock1 = ""
		self.plugs.append(Plug(self))
		self.plugs.append(Plug(self))
	
	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock0 = self.plugs[0].sock.path
		if (self.plugs[1].sock is not None):
			self.cfg.sock1 = self.plugs[1].sock.path
		if (self.proc is not None):
			self.need_restart_to_apply_changes = True
	
	def configured(self):
		return (self.plugs[0].sock is not None and self.plugs[1].sock is not None)	
	
	def prog(self):
		return Global.VDEPATH + "/dpipe"
	
	def get_type(self):
		return 'Wire'
	
	def args(self):
		res = []
		res.append(self.prog())
		res.append('vde_plug')
		res.append(self.cfg.sock0)
		res.append('=')
		res.append('vde_plug')
		res.append(self.cfg.sock1)
		return res

class Wirefilter(Wire):
	def __init__(self, _factory, _name):
		Wire.__init__(self, _factory, _name)
		self.command_builder = {"-d":"delay",
					"-l":"loss",
					"-L":"lossburst",
					"-D":"dup",
					"-b":"bandwidth",
					"-s":"speed",
					"-c":"capacity",
					"-n":"noise",
					"-m":"mtu",
					"-N":"nofifo",
					"-M":"console"
			} 
		self.cfg.noise = ""
		self.cfg.capacity = ""
		self.cfg.delayLR = ""
		self.cfg.delayRL = ""
		self.cfg.lossLR = ""
		self.cfg.lossRL = ""
		self.cfg.dupLR = ""
		self.cfg.dupRL = ""
		self.cfg.speedLR = ""
		self.cfg.speedRL = ""
		self.cfg.speedLRunit = ""
		self.cfg.speedRLunit = ""
		self.cfg.speedLRdistribution = ""
		self.cfg.speedRLdistribution = ""
		self.cfg.bandwidthLR = ""
		self.cfg.bandwidthRL = ""
		self.cfg.bandwidthLRunit = ""
		self.cfg.bandwidthRLunit = ""
		self.cfg.bandwidthLRdistribution = ""
		self.cfg.bandwidthRLdistribution = ""

	def args(self):
		res = []
		res.append(self.prog())
		res.append('-v')
		res.append(self.cfg.sock0+":"+self.cfg.sock1)

		if len(self.cfg.delayLR) > 0:
			res.append("-d")
			res.append("LR"+self.cfg.delayLR)
		if len(self.cfg.delayRL) > 0:
			res.append("-d")
			res.append("RL"+self.cfg.delayLR)
		
		if len(self.cfg.lossLR) > 0:
			res.append("-l")
			res.append("LR"+self.cfg.lossLR)
		if len(self.cfg.lossRL) > 0:
			res.append("-l")
			res.append("RL"+self.cfg.lossLR)
		
		if len(self.cfg.dupLR) > 0:
			res.append("-D")
			res.append("LR"+self.cfg.dupLR)
		if len(self.cfg.dupRL) > 0:
			res.append("-D")
			res.append("RL"+self.cfg.dupLR)
		
		if len(self.cfg.speedLR) > 0:
			res.append("-s")
			res.append("LR" + self.cfg.speedLR + self.cfg.speedLRunit + self.cfg.speedLRdistribution)
		if len(self.cfg.speedRL) > 0:
			res.append("-s")
			res.append("RL" + self.cfg.speedRL + self.cfg.speedRLunit + self.cfg.speedRLdistribution)
		
		if len(self.cfg.bandwidthLR) > 0:
			res.append("-s")
			res.append("LR" + self.cfg.bandwidthLR + self.cfg.bandwidthLRunit + self.cfg.bandwidthLRdistribution)
		if len(self.cfg.bandwidthRL) > 0:
			res.append("-s")
			res.append("RL" + self.cfg.bandwidthRL + self.cfg.bandwidthRLunit + self.cfg.bandwidthRLdistribution)

		for param in Brick.build_cmd_line(self):
			res.append(param)
		return res
	
	def prog(self):
		return Global.VDEPATH + "/wirefilter"
	
	def get_type(self):
		return 'Wirefilter'

class TunnelListen(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.active = 0
		self.cfg.name = _name
		self.command_builder = {"-s":'sock', 
			"#password":"password", 
			"-p":"port"
		}
		self.cfg.sock = ""
		self.cfg.password = ""
		self.plugs.append(Plug(self))
		self.cfg.port = "7667"
	

	def prog(self):
		return Global.VDEPATH + "/vde_cryptcab"

	def get_type(self):
		return 'TunnelListen'

	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock = self.plugs[0].sock.path
		if (self.proc is not None):
			self.need_restart_to_apply_changes = True

	def configured(self):
		return (self.plugs[0].sock is not None)	

	def args(self):
		pwdgen="echo %s | sha1sum >/tmp/tunnel_%s.key" % (self.cfg.password, self.name)
		os.system(pwdgen)
		res = [] 
		res.append(self.prog())
		res.append("-P")
		res.append("/tmp/tunnel_%s.key" % self.name)
		for arg in self.build_cmd_line():
			res.append(arg)
		return res	

	def post_poweroff(self):
		os.unlink("/tmp/tunnel_%s.key" % self.name)


class TunnelConnect(TunnelListen):
	def __init__(self, _factory, _name):
		TunnelListen.__init__(self, _factory, _name)
		self.command_builder = {"-s":'sock', 
			"#password":"password", 
			"-p":"localport",
			"-c":"host",
			"#port":"port"
		}
		self.cfg.host = ""
	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock = self.plugs[0].sock.path

		p = self.cfg.get("port")
		if p is not None:
			del(self.cfg.port)
			h = self.cfg.get("host")
			if h is not None:
				h = h.split(":")[0]
				h +=":"+p
				self.cfg.host=h
			
		if (self.proc is not None):
			self.need_restart_to_apply_changes = True
	
	def configured(self):
		return (self.plugs[0].sock is not None) and self.cfg.get("host") and len(self.cfg.host) > 0	
	
	def get_type(self):
		return 'TunnelConnect'

qemu_eth_model = ["rtl8139","e1000","virtio","i82551", "i82557b", "i82559er","ne2k_pci","pcnet","ne2k_isa"]

class VMethernet(Plug, BrickConfig):
	def __init__(self, brick, name):
		Plug.__init__(self, brick)
		self.mac=RandMac()
		self.model='rtl8139'
		self.vlan=len(self.brick.plugs) + len(self.brick.socks) - 1
	

class VM(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.active = 0
		self.cfg.name = _name
		self.command_builder = {
			'-M':'machine',
			'-cpu':'cpu',
			'-smp':'smp',
			#numa not supported
			'-fda':'fda',
			'-fdb':'fdb',
			'-hda':'hda',
			'-hdb':'hdb',
			'-hdc':'hdc',
			'-hdd':'hdd',
			'-cdrom':'cdrom',
			#extended drive: TBD
			'-mtdblock':'mtdblock',
			'-m':'ram',
			'-k':'keyboard',
			'-soundhw':'soundhw',
			'-usb':'usbmode',
			#usbdevice to be implemented as a collection
			#device to be implemented as a collection
			'-name':'name',
			'-uuid':'uuid',
			'-nographic':'nographic',
			'-curses':'curses',
			'-no-frame':'noframe',
			'-no-quit':'noquit',
			'-vga':'vga',
			'-full-screen':'full-screen',
			'-sdl':'sdl',
			'-potrait':'potrait',
			'-win2k-hack':'win2k',
			'-no-acpi':'noacpi',
			'no-hpet':'nohpet',
			'-baloon':'baloon',
			#acpitable not supported
			#smbios not supported
			'-kernel':'kernel',
			'-append':'append',
			'-initrd':'initrd',
			'-serial':'serial',
			'-parallel':'parallel',
			'-monitor':'monitor',
			'-qmp':'qmp',
			'-mon':'',
			'-pidfile':'',
			'-singlestep':'',
			'-S':'',
			'-gdb':'',
			'-s':'',
			'-d':'',
			'-hdachs':'',
			'-L':'',
			'-bios':'',
			'-enable-kvm':'',
			'-no-reboot':'',
			'-no-shutdown':'',
			'-loadvm':'',
			'-daemonize':'',
			'-option-rom':'',
			'-clock':'',
			'-rtc':'',
			'-icount':'',
			'-watchdog':'',
			'-watchdog-action':'',
			'-echr':'',
			'-virtioconsole':'',
			'-show-cursor':'',
			'-tb-size':'',
			'-incoming':'',
			'-nodefaults':'',
			'-chroot':'',
			'-runas':'',
			'-readconfig':'',
			'-writeconfig':'',
			'-no-kvm':'',
			'-no-kvm-irqchip':'',
			'-no-kvm-pit':'',
			'-no-kvm-pit-reinjection':'',
			'-pcidevice':'',
			'-enable-nesting':'',
			'-nvram':'',
			'-tdf':'',
			'-kvm-shadow-memory':'',
			'-mem-path':'',
			'-mem-prealloc':''
		}
	def get_type(self):
		return "Qemu"
	
		
	

class BrickFactory(threading.Thread):
	def __init__(self, showconsole=True):
		self.bricks = []
		self.socks = []
		self.showconsole = showconsole
		threading.Thread.__init__(self)
		self.running_condition = True
		

	def getbrickbyname(self, name):
		for b in self.bricks:
			if b.name == name:
				return b
		return None

	def run(self):
		print "virtualbricks> ",
		sys.stdout.flush()
		p = select.poll()
		p.register(sys.stdin, select.POLLIN)
		while self.running_condition:
			if (self.showconsole):
				if (len(p.poll(10)) > 0):
					command = sys.stdin.readline()
					self.parse(command.rstrip('\n'))
					print
					print "virtualbricks> ",
					sys.stdout.flush()
			else:
				time.sleep(1)
		sys.exit(0)
	def quit(self):
		for b in self.bricks:
			if b.proc is not None:
				b.poweroff()
		print 'Engine: Bye!'
		self.running_condition = False
		sys.exit(0)


	def proclist(self):
		procs = 0
		for b in self.bricks:
			if b.proc is not None:
				procs+=1

			
		if procs > 0:
			print "PID\tType\tname"
			for b in self.bricks:
				if b.proc is not None:
					print "%d\t%s\t%s" % (b.pid,b.get_type(),b.name)
		else:
			print "No process running"

	def parse(self, command):
		if (command == 'q' or command == 'quit'):
			self.quit()
		elif (command == 'h' or command == 'help'):
			print 'no help available'
		elif (command == 'ps'):
			self.proclist()
		
		elif command.startswith('n ') or command.startswith('new '):
			self.newbrick(*command.split(" ")[1:])
		elif command == 'list':
			for obj in self.bricks:
				print "%s %s" % (obj.get_type(), obj.name)
			print "End of list."
			print 			
			
		elif command == 'socks':
			for s in self.socks:
				print "%s" % s.nickname, 
				if s.brick is not None:
					print " - port on %s %s - %d available" % (s.brick.get_type(), s.brick.name, s.get_free_ports())
				else:
					print "not configured."
		else:
			found=None
			for obj in self.bricks:
				if obj.name == command.split(" ")[0]:
					found = obj
					break
			
			if found is not None and len(command.split(" ")) > 1:
				self.brickAction(found, command.split(" ")[1:])
			else:
				print 'Invalid command "%s"' % command	

	def brickAction(self, obj, cmd):
		if (cmd[0] == 'on'):
			obj.poweron()
		if (cmd[0] == 'off'):
			obj.poweroff()
		if (cmd[0] == 'config'):
			obj.configure(cmd[1:])
		if (cmd[0] == 'show'):
			obj.cfg.dump()
		if (cmd[0] == 'connect' and len(cmd) == 2):
			if(self.connect(obj, cmd[1].rstrip('\n'))):
				print ("Connection ok")
			else:
				print ("Connection failed")
		if (cmd[0] == 'disconnect'):
			obj.disconnect()
		if (cmd[0] == 'help'):
			obj.help()

	def connect(self, brick, nick):
		endpoint = None
		if len(nick) == 0:
			return False
		for n in self.socks:
			if n.nickname == nick:
				endpoint = n
		if endpoint is not None:
			return 	brick.connect(endpoint)
		else:
			print "cannot find " + nick
			print self.socks


	
	def newbrick(self, ntype="", name=""):
		for oldb in self.bricks:
			if oldb.name == name:
				raise InvalidNameException
		if ntype == "switch" or ntype == "Switch":
			s = Switch(self,name) 
			print "new switch %s OK" % s.name
		elif ntype == "tap" or ntype == "Tap":
			s = Tap(self,name) 
			print "new tap %s OK" % s.name
		elif ntype == "vm" or ntype == "Qemu":
			s = VM(self, name) 
			print "new vm %s OK" % s.name
		elif ntype == "wire" or ntype == "Wire" or ntype == "Cable":
			s = Wire(self, name) 
			print "new cable %s OK" % s.name
		elif ntype == "wirefilter" or ntype == "Wirefilter":
			s = Wirefilter(self,name) 
			print "new wirefilter %s OK" % s.name
		elif ntype == "tunnell" or ntype == "Tunnel Server":
			s = TunnelListen(self,name) 
			print "new tunnel server %s OK" % s.name
		elif ntype == "tunnelc" or ntype == "Tunnel Client":
			s = TunnelConnect(self,name) 
			print "new tunnel client %s OK" % s.name
		#elif ...:
		else:
			print 'Invalid command.'
			return False
		return True
