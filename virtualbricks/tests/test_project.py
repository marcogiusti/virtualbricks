import os
import StringIO
import operator

from twisted.trial import unittest
from twisted.python import filepath
from twisted.internet import defer

from virtualbricks import settings, project, configfile, errors
from virtualbricks.tests import patch_settings, stubs, failureResultOf


class ArchiveStub:

    create_args = None
    extract_args = None

    def create(self, pathname, files, images=()):
        self.create_args = (pathname, files, images)
        return defer.succeed(None)

    def extract(self, pathname, destination):
        self.extract_args = (pathname, destination)
        return defer.succeed(None)


class TestBase(object):

    def get_manager(self, factory):
        self.tmp = filepath.FilePath(self.mktemp())
        self.tmp.makedirs()
        self.tmp.child("vimages").makedirs()
        patch_settings(self, workspace=self.tmp.path,
                       current_project="new_project")
        manager = project.ProjectManager()
        self.addCleanup(manager.close, factory)
        return manager

    def setUp(self):
        self.factory = stubs.FactoryStub()
        self.manager = self.get_manager(self.factory)


class TestProject(TestBase, unittest.TestCase):

    def assert_initial_status(self):
        self.assertIs(project.current, None)
        self.assertEqual(settings.VIRTUALBRICKS_HOME, settings.DEFAULT_HOME)

    # XXX implement save on restore
    # def test_restore_save(self):
    #     def save_restore(f, prjname):
    #         self.assertIs(f, self.factory)
    #         self.assertTrue(filepath.FilePath(prjname).exists())

    #     self.assert_initial_status()
    #     prj = self.manager.create("test")
    #     self.patch(configfile, "restore", save_restore)
    #     self.patch(configfile, "save", save_restore)
    #     prj.save(self.factory)
    #     prj.restore(self.factory)

    def test_restore_project_set_virtualbricks_home(self):
        """
        Every time a project is imported, settings.VIRTUALBRICKS_HOME is set
        to the project's path.
        """

        self.assert_initial_status()
        self.patch(configfile, "restore", lambda fa, fi: None)
        prj = self.manager.create("test")
        prj.restore(self.factory)
        self.assertEqual(prj.path, settings.VIRTUALBRICKS_HOME)
        self.assertNotEqual(settings.VIRTUALBRICKS_HOME,
                            settings.DEFAULT_HOME)

    def test_open_create_set_current(self):
        """
        Everytime ProjectManager's open or create are called,
        virtualbricks.project.current is set to the current project.
        """

        PROJECT1 = "new1"
        PROJECT2 = "new2"
        self.assert_initial_status()
        self.manager.create(PROJECT1)
        prj1 = self.manager.open(PROJECT1, self.factory)
        self.assertIs(project.current, prj1)
        prj2 = self.manager.create(PROJECT2)
        prj2.restore(self.factory)
        self.assertIs(project.current, prj2)
        prj3 = self.manager.open(PROJECT1, self.factory)
        self.assertIs(project.current, prj3)
        # Two projects returned by two manager.open are different
        self.assertIsNot(prj1, prj3)

    def test_files(self):
        self.assert_initial_status()
        prj = self.manager.create("test")
        files = [prj.filepath.child(".project")]
        self.assertEqual(list(prj.files()), files)
        afile = prj.filepath.child("file")
        afile.open("w").close()
        files.append(afile)
        self.assertEqual(sorted(prj.files()), sorted(files))

    def test_copy(self):
        """Create a copy of the project with a different name."""

        NEW_PROJET_NAME = "copy"
        project = self.manager.create("test")
        new = project.copy(NEW_PROJET_NAME, stubs.FactoryStub())
        self.assertTrue(new.filepath.exists())
        self.assertNotEqual(project.filepath, new.filepath)

    def test_rename(self):
        """Rename a project."""

        project = self.manager.create("test")
        old_path = project.filepath
        project.rename("test_rename")
        self.assertEqual(project.name, "test_rename")
        self.assertTrue(project.filepath.exists())
        self.assertFalse(old_path.exists())

    def test_rename_invalid(self):
        """If an invalid name is given an exception is raised."""

        project = self.manager.create("test")
        self.assertRaises(errors.InvalidNameError, project.rename,
                          "test/invalid")

    def test_rename_invalid_pathological(self):
        """If the name is really strange, the error is not raised."""

        project = self.manager.create("test")
        project.rename("test/../invalid")
        self.assertEqual(project.name, "invalid")

    def test_rename_exists(self):
        """If a project with the same name exists an exception is raised."""

        project = self.manager.create("test")
        project = self.manager.create("test2")
        self.assertRaises(errors.ProjectExistsError, project.rename,
                          "test2")

    def test_save(self):
        """Save a project."""

        project = self.manager.create("test")
        data = project.dot_project().getContent()
        self.factory.new_brick("vm", "test")
        project.save(self.factory)
        self.assertNotEqual(project.dot_project().getContent(), data)

    def test_description(self):
        """Return a description of brand new project."""

        project = self.manager.create("test")
        self.assertEqual(project.get_description(), "")

    def test_set_description(self):
        """Set the description of a project."""

        DESCRIPTION = "hello world"
        prj = self.manager.create("test")
        prj.set_description(DESCRIPTION)
        self.assertEqual(prj.get_description(), DESCRIPTION)

    def test_save_description(self):
        """Save the description when the project is saved."""

        DESCRIPTION = "hello world"
        prj = self.manager.create("test")
        prj.set_description(DESCRIPTION)
        self.assertFalse(prj.get_readme().exists())
        prj.save(self.factory)
        self.assertEqual(prj.get_readme().getContent(), DESCRIPTION)

    def test_delete(self):
        """Delete a project."""

        prj = self.manager.create("test")
        path = prj.path
        self.assertTrue(prj.filepath.exists())
        prj.delete()
        self.assertFalse(os.path.isdir(path))


class TestProjectManager(TestBase, unittest.TestCase):

    def create_project(self, name):
        prj = self.manager.create(name)
        return prj.filepath

    def test_iter(self):
        """Returns only prooved projects."""

        # a file is not a project
        self.tmp.child("child1").touch()
        self.manager.create("prj1")
        # a directory without a .project file is not a project
        self.tmp.child("prj2").makedirs()
        self.assertEqual(list(self.manager), ["prj1"])

    def test_open_project(self):
        """Simple open test."""

        prjpath = self.create_project("prj1")
        prj = self.manager.open("prj1", self.factory)
        self.assertTrue(isinstance(prj, project.Project))
        self.assertEqual(prj.filepath, prjpath)

    def test_open_project_invalid_name(self):
        """Name could not contains path traversal."""

        self.assertRaises(errors.InvalidNameError, self.manager.open,
                          "../ciccio", None)

    def test_open_project_does_not_exists(self):
        """Try to open a project that does not exists."""

        self.assertRaises(errors.ProjectNotExistsError, project.manager.open,
                          "project", self.factory)

    def test_open_project_does_not_exists_dot_project(self):
        """Try to open a project but the .project file does not exists."""

        path = self.create_project("project")
        path.child(".project").remove()
        self.assertFalse(path.child(".project").isfile())
        self.assertRaises(errors.ProjectNotExistsError, project.manager.open,
                          "project", self.factory)

    def test_create_project(self):
        """Create a project."""

        self.assertEqual(settings.get("current_project"), "new_project")
        prj = self.manager.create("prj")
        self.assertNotEqual(settings.get("current_project"), prj.name)
        self.assertTrue(prj.dot_project().isfile())

    def test_create_project_already_exists(self):
        """Create a project but it exists already."""

        self.manager.create("prj")
        self.assertRaises(errors.ProjectExistsError, self.manager.create,
                          "prj")

    def test_restore_last_project(self):
        """Restore last used project."""

        settings.set("current_project", "prj")
        self.manager.create("prj")
        prj = project.restore_last(self.factory)
        self.assertEqual(prj.name, "prj")

    def test_restore_last_project_not_exists(self):
        """
        If the last project does not exists, don't create a new one with the
        same name but use a default name.
        """

        settings.set("current_project", "prj")
        self.assertFalse(self.tmp.child("prj").isdir())
        prj = project.restore_last(self.factory)
        self.assertEqual(prj.name, settings.DEFAULT_PROJECT + "_0")

    def test_delete_project(self):
        """If a project does not exists, the error is not raised."""

        fp = self.tmp.child("prj")
        self.assertFalse(fp.exists())
        self.manager.delete("prj")
        self.manager.create("prj")
        fp.changed()
        self.assertTrue(fp.exists())
        self.assertTrue(fp.child(".project").exists())
        self.manager.delete("prj")
        fp.changed()
        self.assertFalse(fp.exists())

    def test_extract_project_exists(self):
        """
        Extract a project but a project with the same name already exists.
        """

        PRJNAME = "test"
        self.create_project(PRJNAME)
        vbppath = os.path.join(os.path.dirname(__file__), "test.vbp")
        d = self.manager.extract(PRJNAME, vbppath)
        failureResultOf(self, d, errors.ProjectExistsError)

    def test_exists(self):
        """Test the existance of a project."""

        NAME = "test"
        self.assertFalse(self.manager.exists(NAME))
        self.manager.create(NAME)
        self.assertTrue(self.manager.exists(NAME))

    def test_exists_bizarre_name(self):
        self.assertRaises(errors.InvalidNameError, self.manager.exists,
                          "test/bizarre")


class TestTarArchive(unittest.TestCase):

    def setUp(self):
        self.exe = None
        self.args = []
        self.environ = None
        self.archive = project.BsdTgz()
        self.tmp = self.mktemp()
        self.patch(settings, "VIRTUALBRICKS_HOME", self.tmp)

    def run_process(self, exe, args, environ):
        self.exe = exe
        self.args = args
        self.environ = environ
        return defer.Deferred()

    def test_create(self):
        """Create a simple archive."""

        self.archive.create("test.tgz", ["a", "b"],
                            run=self.run_process)
        self.assertEqual(self.args, ["cfzh", "test.tgz", "-C", self.tmp, "a",
                                     "b"])

    def test_create_images(self):
        """Create an archive with images."""

        tmp = filepath.FilePath(self.mktemp())
        tmp.makedirs()
        a = tmp.child("a")
        a.touch()
        b = tmp.child("b")
        b.touch()
        files = ["a", "b"]
        images = [("img_a", a.path), ("img_b", b.path)]
        self.archive.create("test.tgz", files, images, self.run_process)
        expected = ["cfzh", "test.tgz", "-C", self.tmp, "a", "b",
                    ".images/img_a", ".images/img_b"]
        self.assertEqual(self.args, expected)


PROJECT = """[Image:test_qcow2.qcow2]
path = /images/test qcow2.qcow2

[Image:vtatpa.martin.qcow2]
path = /images/vtatpa.martin.qcow2

[Qemu:test]
hda = vtatpa.martin.qcow2
name = test
privatehda = *
snapshot = *
use_virtio = *

link|sender|sw1|rtl8139|00:11:22:33:44:55
"""


class PseudoOerderedDict(dict):

    def __init__(self, arg):
        super(PseudoOerderedDict, self).__init__(arg)
        self._order = map(operator.itemgetter(0), arg)

    def __iter__(self):
        return iter(self._order)


class TestProjectEntry(unittest.TestCase):

    def setUp(self):
        self.entry = project.ProjectEntry.from_fileobj(StringIO.StringIO(
            PROJECT))

    def test_get_images(self):
        self.assertEqual(self.entry.get_images(),
                         [(('Image', 'test_qcow2.qcow2'),
                           {'path': '/images/test qcow2.qcow2'}),
                          (('Image', 'vtatpa.martin.qcow2'),
                           {'path': '/images/vtatpa.martin.qcow2'})])

    def test_get_virtualmachines(self):
        self.assertEqual(self.entry.get_virtualmachines(),
                         [(("Qemu", "test"),
                           {"hda": "vtatpa.martin.qcow2",
                            "name": "test",
                            "privatehda": "*",
                            "snapshot": "*",
                            "use_virtio": "*"})])

    def test_get_disks(self):
        self.assertEqual(self.entry.get_disks(),
                         {"test": [("hda", "vtatpa.martin.qcow2")]})

    def test_device_for_image_empty(self):
        devs = list(self.entry.device_for_image("test_qcow2.qcow2"))
        self.assertEqual([], devs)

    def test_device_for_image(self):
        devs = list(self.entry.device_for_image("vtatpa.martin.qcow2"))
        self.assertEqual([("test", "hda")], devs)

    def test_dump(self):
        sections = {
            ("Image", "test_qcow2.qcow2"): {
                "path": "/images/test qcow2.qcow2"
            },
            ("Image", "vtatpa.martin.qcow2"): {
                "path": "/images/vtatpa.martin.qcow2"
            },
            ("Qemu", "test"): PseudoOerderedDict([
                ("hda", "vtatpa.martin.qcow2"),
                ("name", "test"),
                ("privatehda", "*"),
                ("snapshot", "*"),
                ("use_virtio", "*"),
            ]),
        }
        links = [("link", "sender", "sw1", "rtl8139", "00:11:22:33:44:55")]
        sio = StringIO.StringIO()
        project.ProjectEntry(sections, links).dump(sio)
        self.assertEquals(sio.getvalue(), PROJECT)
