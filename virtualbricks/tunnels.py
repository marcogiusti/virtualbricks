#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Virtualbricks - a vde/qemu gui written in python and GTK/Glade.
Copyright (C) 2011 Virtualbricks team

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; version 2.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import copy
import gobject
import os
import re
import select
import socket
import subprocess
import sys
from virtualbricks.bricks import Brick
from virtualbricks.link import Sock, Plug

class TunnelListen(Brick):
	def __init__(self, _factory, _name):
		Brick.__init__(self, _factory, _name)
		self.pid = -1
		self.cfg.name = _name
		self.command_builder = {"-s":'sock',
			"#password":"password",
			"-p":"port"
		}
		self.cfg.sock = ""
		self.cfg.password = ""
		self.plugs.append(Plug(self))
		self.cfg.port = "7667"

	def restore_self_plugs(self):
		self.plugs.append(Plug(self))

	def clear_self_socks(self, sock=None):
		self.cfg.sock=""

	def get_parameters(self):
		if self.plugs[0].sock:
			return _("plugged to") + " " + self.plugs[0].sock.brick.name + " " +\
				_("listening to udp:") + " " + str(self.cfg.port)
		return _("disconnected")

	def prog(self):
		return self.settings.get("vdepath") + "/vde_cryptcab"

	def get_type(self):
		return 'TunnelListen'

	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock = self.plugs[0].sock.path.rstrip('[]')
		if (self.proc is not None):
			self.need_restart_to_apply_changes = True
		Brick.on_config_changed(self)

	def configured(self):
		return (self.plugs[0].sock is not None)

	def args(self):
		pwdgen = "echo %s | sha1sum >/tmp/tunnel_%s.key && sync" % (self.cfg.password, self.name)
		print "System= %d" % os.system(pwdgen)
		res = []
		res.append(self.prog())
		res.append("-P")
		res.append("/tmp/tunnel_%s.key" % self.name)
		for arg in self.build_cmd_line():
			res.append(arg)
		return res

	#def post_poweroff(self):
	#	os.unlink("/tmp/tunnel_%s.key" % self.name)
	#	pass


class TunnelConnect(TunnelListen):
	def __init__(self, _factory, _name):
		TunnelListen.__init__(self, _factory, _name)
		self.command_builder = {"-s":'sock',
			"#password":"password",
			"-p":"localport",
			"-c":"host",
			"#port":"port"
		}
		self.cfg.sock = ""
		self.cfg.host = ""
		self.cfg.localport = "10771"
		self.cfg.port = "7667"

	def get_parameters(self):
		if self.plugs[0].sock:
			return _("plugged to") + " " + self.plugs[0].sock.brick.name +\
				_(", connecting to udp://") + str(self.cfg.host)

		return _("disconnected")

	def on_config_changed(self):
		if (self.plugs[0].sock is not None):
			self.cfg.sock = self.plugs[0].sock.path.rstrip('[]')

		p = self.cfg.get("port")
		if p is not None:
			h = self.cfg.get("host")
			if h is not None:
				h = h.split(":")[0]
				h += ":" + p
				self.cfg.host = h

		if (self.proc is not None):
			self.need_restart_to_apply_changes = True

		Brick.on_config_changed(self)

	def configured(self):
		return (self.plugs[0].sock is not None) and self.cfg.get("host") and len(self.cfg.host) > 0

	def get_type(self):
		return 'TunnelConnect'

