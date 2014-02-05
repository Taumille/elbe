#!/usr/bin/env python
#
# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2013  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import time
import shutil
from optparse import OptionParser
from treeutils import etree

import elbepack
from elbepack.treeutils import etree
from elbepack.validate import validate_xml
from elbepack.xmldefaults import ElbeDefaults
from elbepack.version import elbe_version

def remove_noerr(name):
    try:
        os.remove(name)
    except:
        pass

def cat_file(inf, outf):
     try:
         f = open(inf)
         outf.write(f.read())
         f.close()
     except IOError:
         pass

def run_command(argv):

    oparser = OptionParser(usage="usage: %prog create-target-rfs [options] <xmlfile>")
    oparser.add_option( "-t", "--target", dest="target",
                         help="directoryname of target" )
    oparser.add_option( "-d", "--debug", dest="debug", default=False,
                         help="additional debug output" )
    oparser.add_option( "-b", "--buildchroot", dest="buildchroot", default=False, action = 'store_true',
                         help="copy kernel to /opt/elbe" )
    oparser.add_option( "-o", "--output", dest="output",
                         help="name of logfile" )
    oparser.add_option("--buildtype", dest="buildtype",
            help="Override the buildtype" )

    (opt, args) = oparser.parse_args(argv)
    if len(args) != 1:
        print "wrong number of arguments"
        oparser.print_help()
        sys.exit(1)

    if not opt.target:
        print "Missing target (-t)"
        sys.exit(1)

    if not validate_xml(args[0]):
        print "xml validation failed. Bailing out"
        sys.exit(20)

    xml = etree(args[0] )
    prj = xml.node("/project")
    tgt = xml.node("/target")

    target = os.path.abspath(opt.target)

    if opt.buildtype:
        buildtype = opt.buildtype
    elif xml.has( "project/buildtype" ):
        buildtype = xml.text( "/project/buildtype" )
    else:
        buildtype = "nodefaults"
    defs = ElbeDefaults(buildtype)

    shutil.rmtree(target, True)
    os.makedirs(target)

    # create filelists describing the content of the target rfs
    do_rsync = True
    filelist = open("/opt/elbe/filelist", "w+")
    if tgt.has("tighten"):
        f = open("/opt/elbe/pkg-list")
        for line in f:
            line = line.rstrip("\n");
            cat_file("/var/lib/dpkg/info/%s.list" %(line), filelist)
            cat_file("/var/lib/dpkg/info/%s.conffiles" %(line), filelist)
        f.close()

    elif tgt.has("diet"):

        arch = xml.text("project/buildimage/arch", default=defs, key="arch")
        os.system("apt-rdepends `cat /opt/elbe/pkg-list` | grep -v \"^ \" | uniq >/opt/elbe/allpkg-list")
        f = open("/opt/elbe/allpkg-list")
        for line in f:
            line = line.rstrip("\n");

            cat_file("/var/lib/dpkg/info/%s.list" %(line), filelist)
            cat_file("/var/lib/dpkg/info/%s.conffiles" %(line), filelist)

            cat_file("/var/lib/dpkg/info/%s:%s.list" %(line), filelist, arch)
            cat_file("/var/lib/dpkg/info/%s:%s.conffiles" %(line), filelist, arch)
        f.close()
        os.remove("/opt/elbe/allpkg-list")
    else:
        os.system("ls -A1 / | grep -v target | grep -v proc | grep -v sys | xargs find | grep -v \"^opt/elbe\" >> /opt/elbe/filelist")
    filelist.close()

    # create target rfs
    os.chdir("/")
    if do_rsync:
        os.system("rsync -a --files-from=/opt/elbe/filelist / %s" %(target))

    os.makedirs("%s/proc" %(target))
    os.makedirs("%s/sys" %(target))

    if tgt.has("setsel"):
        os.system("mount -o bind /proc /%s/proc" %(target))
        os.system("mount -o bind /sys /%s/sys" %(target))

        os.system("chroot /%s dpkg --clear-selections" %(target))
        os.system("chroot /%s dpkg --set-selections </opt/elbe/pkg-selections" %(target))
        os.system("chroot /%s dpkg --purge -a" %(target))

        os.system("umount /%s/proc" %(target))
        os.system("umount /%s/sys" %(target))

    remove_noerr("/etc/elbe_version")

    f = file("/etc/elbe_version", "w+")
    f.write("%s %s" %(prj.text("name"), prj.text("version")))
    f.write("this RFS was generated by elbe %s" % (elbe_version))
    f.write(time.strftime("%c"))
    f.close()

    remove_noerr("/opt/elbe/dump.log")

    cmdline = "elbe dump --name \"%s\" --output /opt/elbe/elbe-report.txt" %(prj.text("name"))
    cmdline += " --validation /opt/elbe/validation.txt --target /%s" %(target)
    cmdline += " --finetuning /opt/elbe/finetuning.sh"
    cmdline += " --kinitrd \"%s\" /opt/elbe/source.xml" %(prj.text("buildimage/kinitrd"))
    if xml.has("archive"):
        cmdline += " --archive /opt/elbe/archive.tar.bz2"
    cmdline += " >> /opt/elbe/dump.log 2>&1"
    os.system(cmdline)

    f = file("/opt/elbe/licence.txt", "w+")
    for dir in os.listdir("/usr/share/doc/"):
        fulldir = os.path.join("/usr/share/doc/", dir)
        if os.path.islink(fulldir):
            continue
        if not os.path.isdir(fulldir):
            continue
        try:
            lic = open(os.path.join(fulldir, "copyright"), "r")
            f.write(dir)
            f.write(":\n================================================================================")
            f.write("\n")
            f.write(lic.read())
            f.write("\n\n")
        except IOError as e:
            os.system("echo Error while processing license file %s: '%s' >> /opt/elbe/elbe-report.txt" %
                    (os.path.join(fulldir, "copyright"), e.strerror))
        finally:
            lic.close()
    f.close()

    # create target images and copy the rfs into them
    os.system("/opt/elbe/part-target.sh >> /opt/elbe/elbe-report.txt 2>&1")

    if xml.has("target/package/tar"):
        os.system("tar cf /opt/elbe/target.tar -C /%s ." %(target))
        os.system("echo /opt/elbe/target.tar >> /opt/elbe/files-to-extract")

    if xml.has("target/package/cpio"):
        cpio_name = xml.text("target/package/cpio/name")
        os.chdir(target)
        os.system("find . -print | cpio -ov -H newc >/opt/elbe/%s" % cpio_name)
        os.system("echo /opt/elbe/%s >> /opt/elbe/files-to-extract" % cpio_name)
        os.chdir("/")

    os.system("echo '' >> /opt/elbe/elbe-report.txt")
    os.system("echo '' >> /opt/elbe/elbe-report.txt")
    os.system("echo 'output of dump.py' >> /opt/elbe/elbe-report.txt")
    os.system("echo '-----------------' >> /opt/elbe/elbe-report.txt")
    os.system("cat /opt/elbe/dump.log   >> /opt/elbe/elbe-report.txt")

    os.system("echo '' >> /opt/elbe/elbe-report.txt")
    os.system("echo '' >> /opt/elbe/elbe-report.txt")
    os.system("echo built with elbe v%s >> /opt/elbe/elbe-report.txt" % (elbe_version))

    os.system("echo /opt/elbe/licence.txt >> /opt/elbe/files-to-extract")
    os.system("echo /opt/elbe/elbe-report.txt >> /opt/elbe/files-to-extract")
    os.system("echo /opt/elbe/source.xml >> /opt/elbe/files-to-extract")
    os.system("echo /opt/elbe/validation.txt >> /opt/elbe/files-to-extract")

    if opt.debug:
        os.system("echo /var/log/syslog >> /opt/elbe/files-to-extract")

    if not opt.buildchroot:
        if xml.text("project/buildimage/arch", default=defs, key="arch") == "armel":
            os.system("cp -L /boot/vmlinuz /opt/elbe/vmkernel")
            os.system("cp -L /boot/initrd.img /opt/elbe/vminitrd")
        elif xml.text("project/buildimage/arch", default=defs, key="arch") == "powerpc":
            os.system("cp -L /boot/vmlinux /opt/elbe/vmkernel")
            os.system("cp -L /boot/initrd.img /opt/elbe/vminitrd")
        else:
            os.system("cp -L /vmlinuz /opt/elbe/vmkernel")
            os.system("cp -L /initrd.img /opt/elbe/vminitrd")

if __name__ == "__main__":
    run_command(sys.argv[1:])
