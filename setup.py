#!/usr/bin/env python

from distutils.core import setup

setup(name='Sharescanner',
	version='0.1.0',
	description='A GTK tool for scanning network shares and downloading files from them',
	author='Yavor Stoychev',
	author_email='stoychev.yavor@gmail.com',
	url='http://sourceforge.net/projects/share-scanner/',
	packages=['sharescanner'],
	scripts=['bin/sharescanner.py'],
	data_files=[('/usr/share/icons', ['sharescanner.png']),
		('/usr/share/sharescanner', ['sharescanner.ui']),
		('/usr/share/applications', ['sharescanner.desktop']),
		('/usr/share/glib-2.0/schemas', ['apps.sharescanner.gschema.xml'])],
    install_requires=[
        "smbc >= 1.0.6",
        "gi >= 0.0.0"],
	classifiers=[
	'Development Status :: 5 - Production/Stable',
	'Environment :: X11 Applications :: Gnome',
	'Environment :: X11 Applications :: GTK',
	'Intended Audience :: End Users/Desktop',
	'Intended Audience :: System Administrators',
	'License :: OSI Approved :: GNU General Public License (GPL)',
	'Operating System :: POSIX :: Linux',
	'Programming Language :: Python :: 2.7',
	'Topic :: Desktop Environment :: Gnome']
	)
