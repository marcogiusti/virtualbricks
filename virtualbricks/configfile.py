# -*- test-case-name: virtualbricks.tests.test_configfile -*-
# Virtualbricks - a vde/qemu gui written in python and GTK/Glade.
# Copyright (C) 2013 Virtualbricks team

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import os.path
import errno
import traceback
import contextlib

from twisted.python import filepath

from virtualbricks import settings, configparser, log


if False:  # pyflakes
    _ = str


logger = log.Logger()
link_type_error = log.Event("Cannot find link of type {type}")
brick_not_found = log.Event("Cannot find brick {brick}, skipping line {line}")
sock_not_found = log.Event("Cannot find sock {sockname}, skipping line {line}")
link_added = log.Event("Added {type} to {brick}")
cannot_save_backup = log.Event("Cannot save to backup file {filename}.\n"
                               "{traceback}")
project_saved = log.Event("Saved project to {filename}.")
cannot_restore_backup = log.Event("Cannot restore backup file {filename}.\n"
                                  "{traceback}")
backup_restored = log.Event("A backup file for the current project has been "
                            "restored.\nYou can find more informations "
                            "looking in View->Messages.")
image_found = log.Event("Found Disk image {name}")
skip_image = log.Event("Skipping disk image, name '{name}' already in use")
skip_image_noa = log.Event("Cannot access image file, skipping")
config_dump = log.Event("CONFIG DUMP on {path}")
open_project = log.Event("Open project at {path}")
config_save_error = log.Event("Error while saving configuration file")

log_events = [link_type_error,
              brick_not_found,
              sock_not_found,
              link_added,
              cannot_save_backup,
              project_saved,
              cannot_restore_backup,
              backup_restored,
              image_found,
              skip_image,
              skip_image_noa,
              config_dump,
              open_project,
              config_save_error]


@contextlib.contextmanager
def backup(original, fbackup):
    try:
        original.copyTo(fbackup)
    except OSError as e:
        if e.errno == errno.ENOENT:
            yield
    else:
        yield
        fbackup.remove()


def restore_backup(filename, fbackup):
    filename_back = filename.sibling(filename.basename() + ".back")
    created = False
    try:
        filename.moveTo(filename_back)
        created = True
    except OSError as e:
        if e.errno == errno.ENOENT:
            pass
        else:
            logger.error(cannot_save_backup, filename=filename_back,
                      traceback=traceback.format_exc())
    else:
        logger.info(project_saved, filename=filename_back)
    try:
        fbackup.moveTo(filename)
    except OSError, e:
        if created:
            created = False
            filename_back.moveTo(filename)
        if e.errno == errno.ENOENT:
            pass
        else:
            logger.warn(cannot_restore_backup, filename=fbackup,
                        traceback=traceback.format_exc())
    else:
        logger.warn(backup_restored, show_to_user=True)
    if created:
        filename_back.remove()


class ImageBuilder:

    def __init__(self, factory, name):
        self.factory = factory
        self.name = name

    def load_from(self, section):
        logger.debug(image_found, name=self.name)
        path = dict(section).get("path", "")
        if self.factory.is_in_use(self.name):
            logger.info(skip_image, name=self.name)
        elif not os.access(path, os.R_OK):
            logger.info(skip_image_noa)
        else:
            return self.factory.new_disk_image(self.name, path)


class SockBuilder:

    def __init__(self, factory):
        self.factory = factory

    def load_from(self, sock):
        brick = self.factory.get_brick_by_name(sock.owner)
        if brick:
            brick.add_sock(sock.mac, sock.model)
            logger.info(link_added, type=sock.type, brick=sock.owner)
        else:
            logger.warn(brick_not_found, brick=sock.owner, line="|".join(sock))


class LinkBuilder:

    def __init__(self, factory):
        self.factory = factory

    def load_from(self, link):
        brick = self.factory.get_brick_by_name(link.owner)
        if brick:
            sock = self.factory.get_sock_by_name(link.sockname)
            if sock:
                brick.add_plug(sock, link.mac, link.model)
                logger.info(link_added, type=link.type, brick=link.owner)
            else:
                logger.warn(sock_not_found, sockname=link.sockname,
                            line="|".join(link))
        else:
            logger.warn(brick_not_found, brick=link.owner, line="|".join(link))


class ConfigFile:

    def save(self, factory, str_or_obj):
        """Save the current project.

        @param obj_or_str: The filename of file object where to save the
                           project.
        @type obj_or_str: C{str} or an object that implements the file
                          interface.
        """

        if isinstance(str_or_obj, (basestring, filepath.FilePath)):
            if isinstance(str_or_obj, basestring):
                fp = filepath.FilePath(str_or_obj)
            logger.debug(config_dump, path=fp.path)
            with backup(fp, fp.sibling(fp.basename() + "~")):
                tmpfile = fp.sibling("." + fp.basename() + ".sav")
                with tmpfile.open("w") as fd:
                    self.save_to(factory, fd)
                tmpfile.moveTo(fp)
        else:
            self.save_to(factory, str_or_obj)

    def save_to(self, factory, fileobj):
        for img in factory.disk_images:
            fileobj.write('[Image:' + img.name + ']\n')
            fileobj.write('path=' + img.path + '\n')
            fileobj.write("\n")

        for event in factory.events:
            event.save_to(fileobj)

        socks = []
        plugs = []
        for brick in iter(factory.bricks):
            brick.save_to(fileobj)
            if brick.get_type() == "Qemu":
                socks.extend(brick.socks)
            plugs.extend(brick.plugs)

        for sock in socks:
            t = "sock|{s.brick.name}|{s.nickname}|{s.model}|{s.mac}\n"
            fileobj.write(t.format(s=sock))

        for plug in plugs:
            if plug.brick.get_type() == 'Qemu':
                if plug.configured():
                    t = ("link|{p.brick.name}|{p.sock.nickname}|{p.model}|"
                         "{p.mac}\n")
                else:
                    t = "link|{p.brick.name}||{p.model}|{p.mac}\n"
                fileobj.write(t.format(p=plug))
            elif plug.sock is not None:
                t = "link|{p.brick.name}|{p.sock.nickname}||\n"
                fileobj.write(t.format(p=plug))

    def restore(self, factory, str_or_obj):
        if isinstance(str_or_obj, (basestring, filepath.FilePath)):
            if isinstance(str_or_obj, basestring):
                fp = filepath.FilePath(str_or_obj)
            restore_backup(fp, fp.sibling(fp.basename() + "~"))
            logger.info(open_project, path=fp.path)
            with fp.open() as fd:
                self.restore_from(factory, fd)
        else:
            self.restore_from(factory, str_or_obj)

    def restore_from(self, factory, fileobj):
        for item in configparser.Parser(fileobj):
            if isinstance(item, tuple):  # links
                self.build_link(factory, item.type).load_from(item)
            else:
                self.build_type(factory, item.type, item.name).load_from(item)

    def build_link(self, factory, type):
        if type == "sock":
            return SockBuilder(factory)
        elif type == "link":
            return LinkBuilder(factory)
        else:
            logger.warn(link_type_error, type=type)

    def build_type(self, factory, type, name):
        if type == "Image":
            return ImageBuilder(factory, name)
        elif type == "Event":
            return factory.new_event(name)
        else:
            return factory.new_brick(type, name)


_config = ConfigFile()


def save(factory, filename=None):
    if filename is None:
        filename = os.path.join(settings.get("workspace"),
                                settings.get("current_project"), ".project")
    _config.save(factory, filename)


def safe_save(factory, filename=None):
    try:
        save(factory, filename)
    except Exception:
        logger.exception(config_save_error)


def restore(factory, filename=None):
    if filename is None:
        filename = os.path.join(settings.get("workspace"),
                                settings.get("current_project"), ".project")
    _config.restore(factory, filename)
