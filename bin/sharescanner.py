#!/usr/bin/env python2
#
# sharescanner.py
# Copyright (C) Yavor Stoychev 2011 <stoychev.yavor@gmail.com>
# 
# ShareScanner is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# ShareScanner is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License afloat
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gio, Gtk, Gdk, GdkPixbuf, GObject
import os, sys, smbc, threading, Queue

GObject.threads_init()
Gdk.threads_init()

#Global Constants
###########################################
UI_FILE = "/usr/share/sharescanner/sharescanner.ui"
GSETTINGS_KEY = "apps.sharescanner"

ctx = smbc.Context()
settings = Gio.Settings.new(GSETTINGS_KEY)

if settings.get_string("download-dir") == "~":
	settings.set_string("download-dir", "/home/" + os.getenv('USERNAME'))

class GUI:
	def __init__(self):
		self.scannerExit = threading.Event()
		self.scannerExit.set()

		self.downloaderExit = threading.Event()
		self.downloadQueue = Queue.Queue()

		self.foundItems = 0
		self.queuedItems = 0

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		# [name, size, path, flag, status, offset]
		self.qStore = Gtk.ListStore(str, float, str, GObject.TYPE_PYOBJECT, str, float)

		# [name, size, path]
		self.fStore = Gtk.ListStore(str, float, str)

		self.fFilter = self.fStore.filter_new()
		self.qFilter = self.qStore.filter_new()

		self.fFilter.set_visible_func(self.Filter, self.builder.get_object("fEntry"))
		self.qFilter.set_visible_func(self.Filter, self.builder.get_object("qEntry"))

		self.fSortModel = Gtk.TreeModelSort(model=self.fFilter)
		self.qSortModel = Gtk.TreeModelSort(model=self.qFilter)

		self.fView = Gtk.TreeView(self.fStore)
		self.fView.set_rules_hint(True)
		self.fView.set_model(self.fSortModel)
		self.fView.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

		self.qView = Gtk.TreeView(self.qStore)
		self.qView.set_rules_hint(True)
		self.qView.set_model(self.qSortModel)
		self.qView.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
		
		self.fSizeCell = Gtk.CellRendererText()
		self.qSizeCell = Gtk.CellRendererText()
		self.qProgCell = Gtk.CellRendererProgress()


		# Initialize TreeView Columns
		fNameColumn = Gtk.TreeViewColumn("Name", Gtk.CellRendererText(), text=0)
		fSizeColumn = Gtk.TreeViewColumn("Size", self.fSizeCell, text=1)
		fPathColumn = Gtk.TreeViewColumn("Path", Gtk.CellRendererText(), text=2)

		qNameColumn = Gtk.TreeViewColumn("Name", Gtk.CellRendererText(), text=0)
		qProgColumn = Gtk.TreeViewColumn("Progress", self.qProgCell, text=4)
		qSizeColumn = Gtk.TreeViewColumn("Size", self.qSizeCell, text=1)
		qPathColumn = Gtk.TreeViewColumn("Path", Gtk.CellRendererText(), text=2)

		fNameColumn.set_sort_column_id(0)
		fSizeColumn.set_sort_column_id(1)
		fPathColumn.set_sort_column_id(2)

		qNameColumn.set_sort_column_id(0)
		qProgColumn.set_sort_column_id(5)
		qSizeColumn.set_sort_column_id(1)
		qPathColumn.set_sort_column_id(2)

		fSizeColumn.set_cell_data_func(self.fSizeCell, Size)
		qSizeColumn.set_cell_data_func(self.qSizeCell, Size)
		qProgColumn.set_cell_data_func(self.qProgCell, Progress)

		fNameColumn.set_resizable(True) 
		fPathColumn.set_resizable(True) 
		fSizeColumn.set_resizable(True) 

		qNameColumn.set_resizable(True) 
		qProgColumn.set_resizable(True) 
		qPathColumn.set_resizable(True)
		qSizeColumn.set_resizable(True) 

		self.fView.append_column(fNameColumn)
		self.fView.append_column(fSizeColumn)
		self.fView.append_column(fPathColumn)

		self.qView.append_column(qNameColumn)
		self.qView.append_column(qProgColumn)
		self.qView.append_column(qSizeColumn)
		self.qView.append_column(qPathColumn)

		self.fView.get_model().connect("row-inserted", self.FilesRowInserted)
		self.fView.get_model().connect("row-deleted", self.FilesRowDeleted)
		self.fView.get_selection().connect("changed", self.FileSelectionChanged)

		self.qView.get_model().connect("row-inserted", self.QueueRowInserted)
		self.qView.get_model().connect("row-deleted", self.QueueRowDeleted)
		self.qView.get_selection().connect("changed", self.QueueSelectionChanged)

		self.builder.get_object("fchooser").set_current_folder(settings.get_string("download-dir"))
		self.builder.get_object("autostart").set_active(settings.get_boolean("autostart"))
		self.builder.get_object("autoclear").set_active(settings.get_boolean("autoclear"))
		self.builder.get_object("threadS").set_value(settings.get_int("max-threads"))
		self.builder.get_object("chunkS").set_value(settings.get_int("chunk-size"))

		self.builder.get_object('fscroll').add(self.fView)
		self.builder.get_object('qscroll').add(self.qView)

		# Initialize Main Window
		self.mainWindow = self.builder.get_object('mainWindow')
		self.mainWindow.show_all()

	def Show(self, window):
		window.run()
		window.hide()

	def ClearSearchText(self, textbox, icon, data):
		textbox.set_text("")

	def ToggleScan(self, button):
		if self.scannerExit.is_set(): #start scan
			self.fStore.clear()
			self.scannerExit.clear()
			thread = threading.Thread(name="scanner", target=self.Scan, args=())
			thread.daemon = True
			thread.start()
			button.set_label("Stop _Scan")
		else:						#stop scan
			self.scannerExit.set()
			print "Scan Cancelled by User"

	def Scan(self, path="smb://"):
		if self.scannerExit.is_set():
			return
		try:
			list = ctx.opendir(path).getdents()
			for e in list:
				if self.scannerExit.is_set():
					break
				if e.name != "" and e.name != " ": # work around a bug in smbc
					if e.smbc_type == 1: 	# workgroup
						self.Scan(path + e.name)
					elif e.smbc_type == 2:	# server
						self.Scan("smb://" + e.name)
					elif (e.smbc_type  == 7 and e.name != "." and e.name != "..") or e.smbc_type == 3: # directory
						self.Scan(path + '/' + e.name)
					elif e.smbc_type == 8: # file
						Gdk.threads_enter()
						self.fStore.prepend([e.name, float(ctx.stat(path + '/' + e.name)[6]), path.replace("smb://", "", 1)])	# [name, size, path]
						Gdk.threads_leave()

			if path == "smb://":
				print "Exiting..."
				Gdk.threads_enter()
				self.builder.get_object("scan").set_label("Start _Scan")
				Gdk.threads_leave()
				self.scannerExit.set()

		except smbc.PermissionError:
			print "Warning: Cannot Scan " + path + " : Permission Error"
		except smbc.TimedOutError:
			print "Warning: Cannot Scan " + path + " : Timed Out"
		except:
			print "Warning: Unknown Error at " + path # Avoid runtime errors because of misconfigured samba servers	
			
		finally: 
			pass # Make sure threads exits


	def Enqueue(self, button):
		self.fView.get_selection().selected_foreach(self.EnqueueFile, None)	

	def EnqueueFile(self, model, p, i, data):
		flag = threading.Event()
		flag.set()
		name = model.get_value(i ,0)
		size = model.get_value(i ,1)
		path = model.get_value(i ,2)
		offset = 0.0

		if settings.get_boolean("autostart"):
			status = "Queued"
		else:
			status = "Paused"

		itr = self.qStore.append([name, size, path, flag, status, offset])

		if settings.get_boolean("autostart"):
			thread = threading.Thread(name="downloader", target=self.Download, args=(itr, name, size, path, flag, offset))
			thread.daemon = True
			if NumThreads() < settings.get_int("max-threads"):
				thread.start()
			else:
				self.downloadQueue.put(thread)

	def Remove(self, button):
		iters = self.GetSelection(self.qView)
 		for i in iters:
			self.qStore.get_value(i, 3).set() # Set Exit Flag
   			self.Del(i)

	def Start(self, button):
		iters = self.GetSelection(self.qView)
 		for i in iters:
			if self.qStore.get_value(i, 3).is_set():
				updateButtons = True
				[name, size, path, flag, status, offset] = self.qStore.get(i, 0, 1, 2, 3, 4, 5)
				self.qStore.set_value(i, 4, "Queued")
				thread = threading.Thread(name="downloader", target=self.Download, args=(i, name, size, path, flag, offset))
				thread.daemon = True
				if NumThreads() < settings.get_int("max-threads"):
					thread.start()
				else:
					self.downloadQueue.put(thread)
			if updateButtons:
				self.builder.get_object("stop").set_sensitive(True)
				
		
		

	def Stop(self, button):
		iters = self.GetSelection(self.qView)
 		for i in iters:
			self.qStore.get_value(i, 3).set()
		self.builder.get_object("start").set_sensitive(True)

	def Clear(self, button):
		iters = self.GetSelection(self.qView)
 		for i in iters:
			if self.qStore.get_value(i, 4) == "Done":
				self.Del(i)

	def Del(self, i):
   			self.qStore.remove(i) # Remove Row


	def Download(self, itr, name, size, path, flag, offset):
		flag.clear()
		Gdk.threads_enter()
		self.qStore.set_value(itr, 4, "Downloading")
		Gdk.threads_leave()
		try:
			inputFile = ctx.open('smb://' + path + '/' + name)
			outputFile = open(settings.get_string("download-dir") + "/" + name, 'w')
			old_progress = 0.0
			new_progress = 0.0
		except:
			print "Error opening files!"			
		while self.downloaderExit.is_set() == False and flag.is_set() == False:
			try:
				chunk = inputFile.read(settings.get_int("chunk-size"))			
				if chunk:
					outputFile.write(chunk)
					offset += settings.get_int("chunk-size")
					new_progress = offset / size
					if old_progress <= new_progress - 0.01: # Don't flood the queue if the change is less than 1%
						Gdk.threads_enter()
						self.qStore.set_value(itr, 5, offset)
						Gdk.threads_leave()
						old_progress = new_progress
				
				else:
					break
			except:
				print "I/O Error!"
				return
		if flag.is_set():
			Gdk.threads_enter()
			self.qStore.set_value(itr, 4, "Paused")
			Gdk.threads_leave()
		else:
			Gdk.threads_enter()
			self.qStore.set_value(itr, 5, size) 
			self.qStore.set_value(itr, 4, "Done")
			if settings.get_boolean("autoclear"):
				self.Del(itr)
			Gdk.threads_leave()
		inputFile.close()

		if NumThreads() <= settings.get_int("max-threads"):
			try:
				self.downloadQueue.get(False).start()
			except Queue.Empty:
				pass
			 

	def GetSelection(self, view):
 		sortedModel, selected = view.get_selection().get_selected_rows()
 		filteredModel = sortedModel.get_model()
 		return [filteredModel.convert_iter_to_child_iter(filteredModel.get_iter(path)) for path in selected]

	def FileSelectionChanged(self, selection):
		self.builder.get_object("enqueue").set_sensitive(False)
		iters = self.GetSelection(selection.get_tree_view())
		if len(iters):
			self.builder.get_object("enqueue").set_sensitive(True)

	def QueueSelectionChanged(self, selection):
		self.UpdateButtonStatus(self.GetSelection(selection.get_tree_view()))

	def UpdateButtonStatus(self, iters):
		self.builder.get_object("start").set_sensitive(False)
		self.builder.get_object("stop").set_sensitive(False)
		self.builder.get_object("clear").set_sensitive(False)
		self.builder.get_object("del").set_sensitive(False)
		if len(iters):
			self.builder.get_object("del").set_sensitive(True)
 		for i in iters:
			if self.qStore.get_value(i, 3).is_set():
				self.builder.get_object("start").set_sensitive(True)
			if self.qStore.get_value(i, 4) == "Downloading":
				self.builder.get_object("stop").set_sensitive(True)
			if self.qStore.get_value(i, 4) == "Done":
				self.builder.get_object("clear").set_sensitive(True)


	def FilesRowInserted(self, model, path, data=None):
		self.foundItems += 1
		self.UpdateFilesLabel()	

	def FilesRowDeleted(self, model, path, data=None):
		self.foundItems -= 1
		self.UpdateFilesLabel()	

	def QueueRowInserted(self, model, path, data=None):
		self.queuedItems += 1
		self.UpdateQueueLabel()
		
	def QueueRowDeleted(self, model, path, data=None):
		self.queuedItems -= 1
		self.UpdateQueueLabel()

	def UpdateFilesLabel(self):
		self.builder.get_object("files").set_text("Network Files (" + str(self.foundItems) + ")")

	def UpdateQueueLabel(self):
		self.builder.get_object("queue").set_text("Queue (" + str(self.queuedItems) + ")")

	def Filter(self, model, iter, entry):
		try:
			value = model.get_value(iter, 0)
			return entry.get_text().lower() in value.lower()
		except AttributeError:
			return True

	def RefilterFiles(self, widget, data=None):
		self.fFilter.refilter()

	def RefilterQueue(self, widget, data=None):
		self.qFilter.refilter()


	def destroy(self, window):
		self.scannerExit.set() 		#Send shutdown signal to scanner process
		Gtk.main_quit()


	def DownloadDirChanged(self, widget):
		settings.set_string("download-dir", widget.get_current_folder())

	def MaxThreadsChanged(self, widget):
		settings.set_int("max-threads", widget.get_value())

	def AutostartChanged(self, widget):
		settings.set_boolean("autostart", widget.get_active())

	def AutoclearChanged(self, widget):
		settings.set_boolean("autoclear", widget.get_active())

	def ChunkSizeChanged(self, widget):
		settings.set_int("chunk-size", widget.get_value())

def main():
	app = GUI()
	Gtk.main()

#Support Functions
###########################################

# Format Size 
def Size(tree_column, cell, model, iter, data):
	lSize = model.get_value(iter, 1)
	sSize = ""
	if lSize > 1000000000.0:
		sSize = str("%.2f" % (lSize / 1000000000.0)) + " GiB"
	elif lSize > 1000000.0:
		sSize = str("%.2f" % (lSize / 1000000.0)) + " MiB"
	elif lSize > 1000.0:
		sSize = str("%.2f" % (lSize / 1000.0)) + " KiB"
	else:
		sSize = str(lSize) + " B"
	cell.set_property("text", sSize)


# Calculate Progress
def Progress(tree_column, cell, model, iter, data):
	offset = model.get_value(iter, 5)
	size = model.get_value(iter, 1)
	if size > 0:
		progress = int(offset * 100.0 / size)
		if progress > 100:
			progress = 100
	else:
		progress = 0
	cell.set_property("value", progress)

def NumThreads(name="downloader"):
		n = 0
		for thread in threading.enumerate():
			if thread.name == name:
				n += 1
		return n

# Entry Point	
if __name__ == "__main__":
    sys.exit(main())
