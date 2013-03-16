===========
Sharescanner
===========

Sharescanner is a tool for indexing network shares. It uses the Python Samba bindings to index all shares with anonymous read access, and shows a searchable list of all files found. Its user interface is designed using glade and the Python GObject bindings (gi). Multiple files can be downloaded simultaneously, and the queue includes status bars and the ability to pause and resume downloads.

Sharescanner does its magic without mounting any shares. 


Installation
=========

To install Sharescanner:

* run 'setup.py install' as root

* run 'glib-compile-schemas /usr/share/glib-2.0/schemas/' as root

* Enjoy!
