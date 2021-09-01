#!/usr/bin/python
# This file's encoding: UTF-8, so that non-ASCII characters can be used in strings.
#
#		███╗   ███╗ ███╗   ███╗ ██╗    ██╗			-------                                                   -------
#		████╗ ████║ ████╗ ████║ ██║    ██║		 # -=======---------------------------------------------------=======- #
#		██╔████╔██║ ██╔████╔██║ ██║ █╗ ██║		# ~ ~ Written by DRGN of SmashBoards (Daniel R. Cappel);  May, 2020 ~ ~ #
#		██║╚██╔╝██║ ██║╚██╔╝██║ ██║███╗██║		 #            [ Built with Python v2.7.16 and Tkinter 8.5 ]            #
#		██║ ╚═╝ ██║ ██║ ╚═╝ ██║ ╚███╔███╔╝		  # -======---------------------------------------------------======- #
#		╚═╝     ╚═╝ ╚═╝     ╚═╝  ╚══╝╚══╝ 			 ------                                                   ------
#		  -  - Melee Modding Wizard -  -  


# External dependencies
import os
import ttk
import time
import wave
import struct
import shutil
import tkFont
import pyaudio
import tkFileDialog
import tkMessageBox
import Tkinter as Tk
from threading import Thread, Event

# Internal dependencies
import globalData
from hsdFiles import MusicFile
from basicFunctions import uHex, humansize, createFolders, msg, cmdChannel
from guiSubComponents import importSingleFileWithGui, getNewNameFromUser, BasicWindow, NeoTreeview


def getHpsFile( windowParent=None, isoPath='' ):

	""" Prompts the user to select an audio file, converts it to HPS format if it is not 
		one already, initializes it as an HPS audio file object, and returns that object. 
		Returns None if the user cancels or the MusicFile object cannot be created. """
	
	# Define formats suitable for MeleeMedia input
	fileTypeOptions = [ ( "HPS files", '*.hps' ), ('DSP files', '*.dsp'), ('WAV files', '*.wav'), ('MP3 files', '*.mp3'), 
						('AIFF files', '*.aiff'), ('WMA files', '*.wma'), ('M4A files', '*.m4a'), ("All files", "*.*") ]
	
	if not windowParent:
		windowParent = globalData.gui.root

	# Prompt the user to choose a file to import
	newFilePath = tkFileDialog.askopenfilename(
		title="Choose an audio file to import; use the filetype dropdown to convert on import",
		parent=windowParent,
		multiple=False,
		initialdir=globalData.getLastUsedDir( 'hps' ),
		filetypes=fileTypeOptions )

	if not newFilePath: # The above will return an empty string if the user canceled
		globalData.gui.updateProgramStatus( 'Operation canceled' )
		return None

	globalData.setLastUsedDir( newFilePath, 'hps' )

	# Convert the file to HPS format, if needed
	if os.path.splitext( newFilePath )[1].lower() != '.hps':
		# Prompt the user to specify a loop point
		loopEditorWindow = LoopEditorWindow( 'Loop Configuration' )
		if loopEditorWindow.loopArg == 'cancel': # User may have canceled the operation
			globalData.gui.updateProgramStatus( 'The operation was canceled.' )
			return None

		# Get the path to the converter executable and construct the output hps filepath
		meleeMediaExe = globalData.paths['meleeMedia']
		newFilename = os.path.basename( newFilePath ).rsplit( '.', 1 )[0] + '.hps'
		outputPath = os.path.join( globalData.paths['tempFolder'], newFilename )
		
		# Convert the file
		command = '"{}" "{}" "{}"{}'.format( meleeMediaExe, newFilePath, outputPath, loopEditorWindow.loopArg )
		returnCode, output = cmdChannel( command )

		if returnCode != 0:
			globalData.gui.updateProgramStatus( 'Conversion failed; {}'.format(output) )
			msg( 'File conversion to HPS format failed; {}'.format(output), 'Conversion Error' )
			return None

		newFilePath = outputPath

	# Initialize the new file
	try:
		newFileObj = MusicFile( None, -1, -1, isoPath, extPath=newFilePath, source='file' )
		newFileObj.getData()
		return newFileObj
	except Exception as err:
		print 'Exception during file replacement;', err
		globalData.gui.updateProgramStatus( 'Unable to replace the file; ' + str(err), error=True )
		return None


class AudioManager( ttk.Frame ):

	""" Info viewer and editor interface for stages in SSBM. """

	def __init__( self, parent, mainGui ):

		ttk.Frame.__init__( self, parent )

		# Add this tab to the main GUI
		mainGui.mainTabFrame.add( self, text=' Audio Manager ' )
		self.audioEngine = mainGui.audioEngine
		self.lastExportFormat = 'hps'
		#self.songs = []
		#self.selectedFile = None
		self.boldFont = tkFont.Font( weight='bold', size=mainGui.defaultFontSize )
		self.normalFont = tkFont.Font( weight='normal' )

		# Construct the left-hand side of the interface, the file list
		treeScroller = Tk.Scrollbar( self )
		self.fileTree = NeoTreeview( self, columns=('filename'), show='tree', yscrollcommand=treeScroller.set )
		self.fileTree.column( '#0', width=300 )
		self.fileTree.column( 'filename', width=140 )
		self.fileTree.tag_configure( 'playing', foreground='#4030ec', font=self.boldFont ) # Dark blue/Purple
		self.fileTree.tag_configure( 'changed', foreground='red' )
		self.fileTree.tag_configure( 'changesSaved', foreground='#292' ) # The 'save' green color
		self.fileTree.grid( column=0, row=0, sticky='ns' )
		treeScroller.config( command=self.fileTree.yview )
		treeScroller.grid( column=1, row=0, sticky='ns' )

		# Construct the right-hand side of the interface, the info panels
		infoPane = ttk.Frame( self )

		generalLabelFrame = ttk.LabelFrame( infoPane, text='  General Info  ', labelanchor='n', padding=(20, 0, 20, 4) ) # Padding order: Left, Top, Right, Bottom.
		ttk.Label( generalLabelFrame, text=('Total Tracks:\nTotal Filespace:') ).pack( side='left' )
		self.generalInfoLabel = ttk.Label( generalLabelFrame )
		self.generalInfoLabel.pack( side='right', padx=6 )
		generalLabelFrame.pack( pady=(12, 6) )
		
		trackInfoLabelFrame = ttk.LabelFrame( infoPane, text='  Track Info  ', labelanchor='n', padding=(20, 0, 20, 4) )
		ttk.Label( trackInfoLabelFrame, text=('Music ID:\nFile Size:\nSample Rate:\nChannels:\nDuration:\nLoop Point:') ).pack( side='left' )
		self.trackInfoLabel = ttk.Label( trackInfoLabelFrame, width=22 )
		self.trackInfoLabel.pack( side='right', padx=6 )
		# Show/Edit loop point
		trackInfoLabelFrame.pack( pady=6 )
		
		# emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
		# self.controlsFrame = ttk.Labelframe( infoPane, labelwidget=emptyWidget, padding=(20, 4) )
		self.controlsFrame = ttk.Frame( infoPane )
		ttk.Button( self.controlsFrame, text='Export', command=self.exportTrack, state='disabled' ).grid( column=0, row=0, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Import', command=self.importTrack, state='disabled' ).grid( column=1, row=0, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Rename', command=self.rename, state='disabled' ).grid( column=0, row=1, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Edit Loop', command=self.editLoop, state='disabled' ).grid( column=1, row=1, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Delete', command=self.delete, state='disabled' ).grid( column=0, row=2, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Add Track', command=self.addTrack ).grid( column=1, row=2, padx=5, pady=5 )
		ttk.Button( self.controlsFrame, text='Look for References', command=self.findReferences ).grid( column=0, row=3, columnspan=2, ipadx=10, padx=5, pady=5 )
		self.controlModule = AudioControlModule( self.controlsFrame, self.audioEngine )
		self.controlModule.grid( column=0, columnspan=2, row=4, padx=5, pady=5 )
		self.controlsFrame.pack( pady=6 )

		self.referencesList = ttk.Label( infoPane, wraplength=400 )
		self.referencesList.pack( pady=6 )

		# Add treeview event handlers
		self.fileTree.bind( '<<TreeviewSelect>>', self.onFileTreeSelect )
		self.fileTree.bind( '<Double-1>', self.controlModule.playAudio ) # The above should also happen first by default
		#self.fileTree.bind( "<3>", self.createContextMenu ) # Right-click

		infoPane.grid( column=2, row=0, sticky='n' )
		
		self.columnconfigure( 0, weight=0 )
		self.columnconfigure( 1, weight=0 )
		self.columnconfigure( 2, weight=1 )
		self.rowconfigure( 'all', weight=1 )

	def clear( self ):

		""" Clears this tab's GUI contents and stops audio playback. """

		if self.audioEngine.audioThread:
			self.audioEngine.stop()

		self.controlModule.audioFile = None

		# Delete the current items in the tree
		for item in self.fileTree.get_children():
			self.fileTree.delete( item )

		self.generalInfoLabel['text'] = ''
		self.trackInfoLabel['text'] = ''
		self.referencesList['text'] = ''

		# Update the main control buttons (to a state of no item is selected)
		for widget in self.controlsFrame.winfo_children():
			if widget.winfo_class() == 'TButton':
				if widget['text'] == 'Add Track':
					widget['state'] = 'normal'
				else:
					widget['state'] = 'disabled'

	def loadFileList( self, restoreState=True ):

		""" Load music files from the currently loaded disc into this tab. """

		if restoreState:
			self.fileTree.saveState()

		self.clear()

		# Get the list of songs from the disc
		#self.songs = []
		filecount = 0
		totalFilesize = 0
		for musicFile in globalData.disc.files.itervalues():
			# Ignore non music files
			if not musicFile.__class__.__name__ == 'MusicFile':
				continue

			#self.songs.append( musicFile )
			filecount += 1
			totalFilesize += musicFile.size
		
			# Add labels along the left for the songs found above
			if musicFile.isHexTrack: # These are 20XX's added custom tracks, e.g. 01.hps, 02.hps, etc.
				if not self.fileTree.exists( 'hextracks' ):
					self.fileTree.insert( '', 'end', iid='hextracks', text=' Hex Tracks  (20XX Custom Music)', values=('', 'cFolder'), image=globalData.gui.imageBank('musicIcon') )
				parent = 'hextracks'
			elif musicFile.filename.startswith( 'ff_' ):
				if not self.fileTree.exists( 'fanfare' ):
					self.fileTree.insert( '', 'end', iid='fanfare', text=' Fanfare  (Victory Audio Clips)', values=('', 'cFolder'), image=globalData.gui.imageBank('audioIcon') )
				parent = 'fanfare'
			else:
				parent = ''

			# Add the musicFile to the treeview
			self.fileTree.insert( parent, 'end', iid=musicFile.isoPath, text=musicFile.description, values=(musicFile.filename, 'file') )
			# if musicFile.isHexTrack:
			# 	print humansize(musicFile.size), '  \t', musicFile.description

		if restoreState:
			self.fileTree.restoreState()

		self.updateGeneralInfo( filecount, totalFilesize )

	def getItemsInSelection( self, selectionTuple, recursive=True ):

		""" Extends a selection in the treeview, which may contain folders, to include all files within those folders. 
			"iid"s are unique "Item IDentifiers" given to file/folder items in treeview widgets to identify or select them. """

		fileIids = set()
		folderIids = set()

		# Separate sets/lists of file/folder isoPaths
		for iid in selectionTuple:
			itemType = self.fileTree.item( iid, 'values' )[1] # May be "file", "nFolder" (native folder), or "cFolder" (convenience folder)

			if itemType != 'file':
				folderIids.add( iid )

				if recursive:
					subFolderItems = self.fileTree.get_children( iid )
					subFolders, subFiles = self.getItemsInSelection( subFolderItems, True )
					folderIids.update( subFolders )
					fileIids.update( subFiles )
			else:
				fileIids.add( iid )

		return folderIids, fileIids

	def getSelectedFile( self ):

		iidSelectionsTuple = self.fileTree.selection()
		if len( iidSelectionsTuple ) != 1:
			return None

		# Attempt to get the associated audio file object
		isoPath = iidSelectionsTuple[0]
		musicFile = globalData.disc.files.get( isoPath )

		if not musicFile: # This was probably a folder that was clicked on (being in the fileTree list means the file must be in the disc)
			globalData.gui.updateProgramStatus( 'No file is selected' )
		
		return musicFile

	def updateGeneralInfo( self, filecount=0, totalFilesize=0 ):

		if not filecount:
			# for fileObj in self.songs:
			# 	totalFilesize += fileObj.size
			
			for musicFile in globalData.disc.files.itervalues():
				# Ignore non music files
				if not musicFile.__class__.__name__ == 'MusicFile':
					continue
				
				filecount += 1
				totalFilesize += fileObj.size
		
		self.generalInfoLabel['text'] = '\n'.join( [str(filecount), humansize(totalFilesize) ] )

	def onFileTreeSelect( self, event=None ):

		""" Called when an item (file or folder) in the Disc File Tree is selected. Iterates over 
			the selected items, calculates total file(s) size, and displays it in the GUI. """

		iidSelectionsTuple = self.fileTree.selection()
		if not iidSelectionsTuple: # Failsafe; not possible?
			return

		# Multiple items selected
		elif len( iidSelectionsTuple ) > 1:
			# Update the main control buttons
			for widget in self.controlsFrame.winfo_children():
				if widget.winfo_class() == 'TButton':
					if widget['text'] in ( 'Export', 'Delete', 'Add Track' ):
						widget['state'] = 'normal'
					else:
						widget['state'] = 'disabled'
			self.trackInfoLabel['text'] = ''
			return
		
		# One item selected; check that it's a file
		musicFile = globalData.disc.files.get( iidSelectionsTuple[0] )
		if not musicFile: return # A folder is likely selected

		# Update the main control buttons
		for widget in self.controlsFrame.winfo_children():
			if widget.winfo_class() == 'TButton':
				if widget['text'] in ( 'Edit Loop' ):
					widget['state'] = 'disabled'
				else:
					widget['state'] = 'normal'
		
		# Read the file and populate the GUI's Track Info section
		musicFile.readBlocks()
		self.controlModule.audioFile = musicFile

		# Build a string for the music ID (some may have two!)
		if musicFile.isHexTrack and musicFile.trackNumber <= 0x30 and musicFile.trackNumber != 0:
			musicId = '0x{:X} | 0x{:X}'.format( musicFile.musicId, musicFile.trackNumber | 0x10000 )
		else:
			musicId = uHex( musicFile.musicId )

		# Format file size and track duration strings
		fileSizeString = '{}   (0x{:X})'.format( humansize(musicFile.size), musicFile.size ) # Displays as MB/KB, and full hex value
		seconds, milliseconds = divmod( musicFile.duration, 1000 )
		minutes, seconds = divmod( seconds, 60 )
		durationString = '{:02}:{:02}.{:03}'.format( int(minutes), int(seconds), int(milliseconds) ) # Will pad minutes/seconds to 2 characters, and milliseconds to 3

		if musicFile.loopPoint == -1:
			loopPointString = 'None'
		elif musicFile.loopPoint == 0:
			loopPointString = '00:00.000 (track start)'
		else:
			seconds, milliseconds = divmod( musicFile.loopPoint, 1000 )
			minutes, seconds = divmod( seconds, 60 )
			loopPointString = '{:02}:{:02}.{:03}'.format( int(minutes), int(seconds), int(milliseconds) ) # Will pad minutes/seconds to 2 characters, and milliseconds to 3

		# Update the Track Info label and clear the references list
		self.trackInfoLabel['text'] = '\n'.join( [musicId, fileSizeString, '{:,} Hz'.format(musicFile.sampleRate), str(musicFile.channels), durationString, loopPointString] )
		self.referencesList['text'] = ''

		# Update the Play/Pause button
		# if self.audioEngine.isPlayingAudio() and self.audio self.audioEngine.audioThread.name == self.controlModule.audioFile.filename: # i.e. this is the file currently playing audio
		# 	self.controlModule.showPauseBtn()
		# else:
		# 	self.controlModule.showPlayBtn()

	def exportTrack( self ):

		""" Exports a single file, while prompting the user on where they'd like to save it. 
			Essentially operates exactly like 'exportSingleFileWithGui', except with the added 
			optional ability to convert the track to WAV format on export, if that extension was 
			chosen. Updates the default directory to search in when opening or exporting files. 
			Also handles updating the GUI with the operation's success/failure status. """

		musicFile = self.getSelectedFile()
		if not musicFile: return

		# Determine the filetype to try to save as by default
		if self.lastExportFormat == 'hps':
			defaultName = musicFile.filename
			fileTypeOptions = [( "HPS files", '*.hps' ), ('WAV files', '*.wav'), ( "All files", "*.*" )]
		else:
			defaultName = musicFile.filename[:-3] + 'wav'
			fileTypeOptions = [('WAV files', '*.wav'), ( "HPS files", '*.hps' ), ( "All files", "*.*" )]
		
		# Add the file description to the filename if that option is turned on
		if globalData.checkSetting( 'exportDescriptionsInFilename' ) and musicFile.description:
			name, ext = os.path.splitext( defaultName )

			# Remove illegal characters
			description = musicFile.description
			for char in description:
				if char in ( '\\', '/', ':', '*', '?', '"', '<', '>', '|' ):
					description.replace( char, '-' )

			defaultName = '{} ({}){}'.format( name, description, ext )

		# Prompt for a place to save the file (will also ask to overwrite an existing file)
		savePath = tkFileDialog.asksaveasfilename(
			title="Where would you like to export the file?",
			parent=globalData.gui.root,
			initialdir=globalData.getLastUsedDir( 'hps' ),
			initialfile=defaultName,
			defaultextension=self.lastExportFormat,
			filetypes=fileTypeOptions )

		# The above will return an empty string if the user canceled
		if not savePath:
			globalData.gui.updateProgramStatus( 'Operation canceled' )
			return

		directoryPath = os.path.dirname( savePath )

		if savePath.lower().endswith( '.wav' ):
			self.lastExportFormat = 'wav'
			successful = False
			try:
				# Convert the file to WAV format
				wavFilePath = musicFile.getAsWav()
				if wavFilePath:
					# Move the newly exported WAV file (in the temp folder) to the user's target location
					shutil.move( wavFilePath, savePath ) # Will attempt to delete the file after the move
					#shutil.copy2( wavFilePath, savePath )
					successful = True
			except WindowsError as err:
				if err.winerror == 32: # Unable to delete the file upon move; may be because it's being used to play audio
					successful = True
			except Exception as err:
				print err
		else:
			self.lastExportFormat = 'hps'

			# Write the file to an external/standalone file
			successful = musicFile.export( savePath )

		# Update the default directory to start in when opening or exporting files.
		globalData.setLastUsedDir( directoryPath, 'hps' )

		if successful:
			globalData.gui.updateProgramStatus( 'File exported successfully.', success=True )
		else:
			globalData.gui.updateProgramStatus( 'Unable to export. Check the error log file for details.', error=True )

	def importTrack( self ):

		""" Replaces an existing audio track file with a new one; prompts the user for 
			a new file and converts it to HPS format if it is not already an HPS file. """

		musicFile = self.getSelectedFile()
		if not musicFile: return

		# Prompt the user to select a new external file to import (and convert/initialize it)
		newMusicFile = getHpsFile( isoPath=musicFile.isoPath )

		if newMusicFile:
			# Replace the selected file in the disc
			globalData.disc.replaceFile( musicFile, newMusicFile )

			# Reload information displayed in the GUI
			self.loadFileList()
			# for i, fileObj in enumerate( self.songs ):
			# 	if fileObj.isoPath == musicFile.isoPath:
			# 		self.songs[i] = newMusicFile
			# 		break
			# self.onFileTreeSelect()
			#self.updateGeneralInfo()

			# Prompt the user to enter a new name for this track
			self.rename()

			# Reload the Disc File Tree to show the new file
			if globalData.gui.discTab:
				globalData.gui.discTab.isoFileTree.item( musicFile.isoPath, tags='changed' )

			# Update the Disc Details Tab
			# detailsTab = globalData.gui.discDetailsTab
			# if detailsTab:
			# 	detailsTab.isoFileCountText.set( "{:,}".format(len(globalData.disc.files)) )
				#detailsTab # todo: disc size as well
			
			# Update program status
			globalData.gui.updateProgramStatus( 'File Replaced. Awaiting Save', success=True )

	def rename( self ):

		""" Prompts the user to enter a new name for the selected file, and updates it in the CSS or yaml file. """

		musicFile = self.getSelectedFile()
		if not musicFile: return

		if musicFile.isHexTrack:
			cssFile = globalData.disc.files.get( globalData.disc.gameId + '/MnSlChr.0sd' )
			if not cssFile:
				msg( "Unable to update CSS with song name; the CSS file (MnSlChr.0sd) could not be found in the disc." )
				globalData.gui.updateProgramStatus( "Unable to update CSS with song name; couldn't find the CSS file in the disc", error=True )
				return
			charLimit = cssFile.checkMaxHexTrackNameLen( musicFile.trackNumber )
			if charLimit == -1:
				msg( "Unable to update CSS with song name; a character limit could not be determined from the CSS song names table." )
				globalData.gui.updateProgramStatus( "Unable to update CSS with song name; a character limit could not be determined", error=True )
				return
		else:
			charLimit = 42 # Arbitrary; don't want it too long though, for readability

		# Prompt the user to enter a new name
		newName = getNewNameFromUser( charLimit, message='Enter a new name:', defaultText=musicFile.description )
		if not newName:
			globalData.gui.updateProgramStatus( 'Name update canceled' )
			return

		# Store the new name to file
		returnCode = musicFile.setDescription( newName )
		
		if returnCode == 0:
			# Update the new name in the Disc File Tree
			globalData.gui.discTab.isoFileTree.item( musicFile.isoPath, values=(newName, 'file'), tags='changed' )

			self.fileTree.item( musicFile.isoPath, text=newName )

			if musicFile.isHexTrack:
				globalData.gui.updateProgramStatus( 'Song name updated in the CSS file', success=True )
			else:
				globalData.gui.updateProgramStatus( 'File name updated in the {}.yaml config file'.format(globalData.disc.gameId), success=True )
		elif returnCode == 1:
			globalData.gui.updateProgramStatus( 'Unable to update name/description in the {}.yaml config file'.format(globalData.disc.gameId), error=True )
		elif returnCode == 2:
			globalData.gui.updateProgramStatus( "Unable to update CSS with the name; couldn't find the CSS file in the disc", error=True )
		elif returnCode == 3:
			globalData.gui.updateProgramStatus( "Unable to update CSS with the name; couldn't save the name to the CSS file", error=True )
		else:
			msg( 'An unrecognized return code was given by .setDescription(): ' + str(returnCode) )

	def editLoop( self ):
		musicFile = self.getSelectedFile()
		if not musicFile: return
		print 'not yet supported'

	def delete( self ):

		""" Removes (deletes) files from the disc, and from the fileTree. 
			Note that the iids which the fileTree widget uses are isoPaths. """

		iidSelectionsTuple = self.fileTree.selection()
		if not iidSelectionsTuple: # Failsafe; not possible?
			return

		# Get all folder and file iids currently selected (the file iids will be isoPaths)
		folderIids, fileIids = self.getItemsInSelection( iidSelectionsTuple )
		print 'folderIids:', folderIids
		print 'fileIids:', fileIids
		discFiles = globalData.disc.files
		fileObjects = []

		# Collect file objects for the isoPaths collected above
		for isoPath in fileIids:
			# Collect a file object from the disc for this path, and remove it from the GUI
			fileObj = discFiles.get( isoPath )
			assert fileObj, 'IsoFileTree displays a missing file! ' + isoPath
			fileObjects.append( fileObj )
			self.fileTree.delete( isoPath )

		# Remove the folders from the GUI
		for iid in folderIids:
			try: self.fileTree.delete( iid )
			except: pass # May have already been removed alongside a parent folder

		# Remove the files from the disc
		globalData.disc.removeFiles( fileObjects )

		self.updateGeneralInfo()

		# Reload the Disc File Tree tab
		discTab = globalData.gui.discTab
		if discTab:
			discTab.loadDisc( updateStatus=False, preserveTreeState=True )
		
		# Update the Disc Details Tab
		detailsTab = globalData.gui.discDetailsTab
		if detailsTab:
			detailsTab.isoFileCountText.set( "{:,}".format(len(globalData.disc.files)) )
			#detailsTab # todo: disc size as well
		
		if len( fileObjects ) == 1:
			globalData.gui.updateProgramStatus( '1 file removed from the disc' )
		else:
			globalData.gui.updateProgramStatus( '{} files removed from the disc'.format(len(fileObjects)) )

	def addTrack( self ):

		""" Spawns a child window to prompt the user for a new external file to add to the disc, 
			which should get the file as an HPS file object (converting if necessary), with an 
			appropriate isoPath and file description (song name). This should also fascilitate 
			adding the file to the GUI and updating appropriate info displays. """

		# If this is for 20XX, check for the first hex track slot not in use
		if globalData.disc.is20XX:
			unusedHexTrackName = ''
			gameId = globalData.disc.gameId

			# Determine where the file will go in the disc/TOC when added
			insertionKey = globalData.disc.gameId + '/audio/1padv.ssm' # Auto-generated would be 'GALE01/audio/us/1padv.ssm'
			insertAfter = False

			# Check for an unused hex track, and set file name suggestions
			for i in range( 1, 0x100 ):
				isoPath = '{}/audio/{:02X}.hps'.format( gameId, i ) # Generates a name like 'GALE01/audio/01.hps'
				if isoPath not in globalData.disc.files:
					unusedHexTrackName = '{:02X}.hps'.format( i )
					break

			# Alert the user if no more hex track slots are available
			if not unusedHexTrackName:
				if not tkMessageBox.askokcancel( 'Hex Tracks Slots Full', "There are no slots available for more Hex Tracks. You'll have "
						'to delete/replace existing Hex Tracks before adding more, or add new songs using standard disc file names. '
						'\n\nDo you want to continue and add a song using a standard name?' ):
					return
		else:
			unusedHexTrackName = ''
			insertionKey = globalData.disc.gameId + '/audio/zs.ssm' # Auto-generated would be 'GALE01/audio/us/1padv.ssm'
			insertAfter = True

		# Spawn a new window/interface to get the new file and other details for a new track
		adderWindow = TrackAdder( 'example.hps', unusedHexTrackName )
		newTrack = adderWindow.hpsFile
		if not newTrack:
			return

		newTrack.insertionKey = insertionKey
		globalData.disc.addFiles( [newTrack], insertAfter )

		# Add the file to the internal file list and GUI for this tab, and update General Info
		# if newTrack.isHexTrack:
		# 	parent = 'hextracks'
		# else:
		# 	parent = ''
		# self.songs.append( newTrack )
		# self.fileTree.insert( parent, 'end', iid=newTrack.isoPath, text=newTrack.description, values=(newTrack.filename, 'file') )
		# self.updateGeneralInfo()
		self.loadFileList()

		# Reload the Disc File Tree to show the new file
		if globalData.gui.discTab:
			globalData.gui.discTab.loadDisc( updateStatus=False, preserveTreeState=True )
			globalData.gui.discTab.isoFileTree.item( newTrack.isoPath, tags='changed' )

		# Update the Disc Details Tab
		detailsTab = globalData.gui.discDetailsTab
		if detailsTab:
			detailsTab.isoFileCountText.set( "{:,}".format(len(globalData.disc.files)) )
			#detailsTab # todo: disc size as well

	def findReferences( self ):

		""" Scans all stage files to find references to the currently selected music file. """
		
		musicFile = self.getSelectedFile()
		if not musicFile: return

		# Get a set of stage files referenced by the game
		#referecedFiles = globalData.disc.checkReferencedStageFiles()
		gameId = globalData.disc.gameId
		gameFiles = globalData.disc.files
		primaryReferences = []
		secondaryReferences = []

		#for filename in referecedFiles: # This will just be a set of filenames, not file objects
		for fileObj in gameFiles.itervalues():
			# Ignore non music files
			if not fileObj.__class__.__name__ == 'StageFile':
				continue

			# Get values from the music table
			fileObj.initialize()
			musicTableStruct = fileObj.getMusicTableStruct()
			values = musicTableStruct.getValues()
			valuesPerEntry = len( values ) / musicTableStruct.entryCount
			
			# Check for primary references; check music IDs in the first table entry
			if musicFile.musicId in values[1:5]:
				primaryReferences.append( fileObj )
				continue # Exclude from secondaries list

			# Check for secondary references; get all song IDs from the music table values beyond the first table entry
			secondaryRefs = []
			for i in range( 1, musicTableStruct.entryCount ):
				# Pick out the external stage ID names to get the names for each entry
				secondaryRefs.extend( values[i*valuesPerEntry+1:i*valuesPerEntry+5] ) # Getting values 1 through 4 of the entry

			# Check if any of the above songs match the currently selected song
			if musicFile.musicId in secondaryRefs:
				secondaryReferences.append( fileObj )

		# Reformat the lists of files to descriptive strings
		primaryReferences = [ '{} ({})'.format(fileObj.filename, fileObj.getDescription(False, False)) for fileObj in primaryReferences ]
		secondaryReferences = [ '{} ({})'.format(fileObj.filename, fileObj.getDescription(False, False)) for fileObj in secondaryReferences ]

		# Display the result in the info pane
		if not primaryReferences and not secondaryReferences:
			self.referencesList['text'] = 'Not referenced by any stage files.'
		elif len( primaryReferences ) + len( secondaryReferences ) == 1:
			if primaryReferences:
				self.referencesList['text'] = 'Only found as a primary reference with ' + primaryReferences[0]
			else:
				self.referencesList['text'] = 'Only found as a secondary reference with ' + secondaryReferences[0]
		else:
			self.referencesList['text'] = ''
			if primaryReferences:
				self.referencesList['text'] = '      Primary references:\n\n' + ', '.join( primaryReferences ).encode( 'utf-8' )
			if secondaryReferences:
				if primaryReferences:
					self.referencesList['text'] += '\n\n'
				self.referencesList['text'] += '      Secondary references:\n\n' + ', '.join( secondaryReferences ).encode( 'utf-8' )


class LoopEditorWindow( BasicWindow ):

	def __init__( self, title='Loop Editor' ):

		BasicWindow.__init__( self, globalData.gui.root, title )
		self.loopArg = ''

		# Loop configuration entry
		self.loopEditor = LoopEditor( self.window )
		self.loopEditor.grid( column=0, columnspan=2, row=0, pady=4 )

		# Ok / Cancel buttons
		ttk.Button( self.window, text='Ok', command=self.submit ).grid( column=0, row=1, ipadx=0, padx=6, pady=(4, 14) )
		ttk.Button( self.window, text='Cancel', command=self.cancel ).grid( column=1, row=1, padx=6, pady=(4, 14) )

		# Move focus to this window (for keyboard control), and pause execution of the calling function until this window is closed.
		self.window.grab_set()
		globalData.gui.root.wait_window( self.window ) # Freezes the GUI until this window is closed.

	def submit( self ):

		""" Attempts to build a MeleeMedia argument with the loop editor's given input. This
			will give the user a message and leave this window open if the input is invalid. """

		try:
			self.loopArg = self.loopEditor.loopArg
		except Exception as err:
			msg( 'Invalid input for a custom loop; {}'.format(err), 'Invalid Loop Input', self.window, error=True )
			return
		
		self.close()

	def cancel( self ):
		self.loopArg = 'cancel' # Can't use an empty string or raise an exception to convey this
		self.close()


class LoopEditor( ttk.Frame ):

	""" A Frame widget to display controls for setting/editing a song's loop point. """

	def __init__( self, *args, **kwargs ):

		ttk.Frame.__init__( self, *args, **kwargs )

		self.loopTrack = Tk.IntVar( value=1 )
	
		ttk.Label( self, text='Loop:' ).grid( column=0, row=0, padx=6, pady=4 )
		ttk.Radiobutton( self, text='None', variable=self.loopTrack, value=0, command=self.toggleTrackLooping ).grid( column=1, row=0, padx=6, pady=4 )
		ttk.Radiobutton( self, text='Normal', variable=self.loopTrack, value=1, command=self.toggleTrackLooping ).grid( column=2, row=0, padx=6, pady=4 )
		ttk.Radiobutton( self, text='Custom', variable=self.loopTrack, value=2, command=self.toggleTrackLooping ).grid( column=3, row=0, padx=6, pady=4 )

		ttk.Label( self, text='Minute:' ).grid( column=0, row=1, padx=6, pady=4 )
		self.minutesEntry = ttk.Entry( self, width=4, state='disabled' )
		self.minutesEntry.grid( column=1, row=1, padx=(18, 6), pady=4 )
		ttk.Label( self, text='Second:' ).grid( column=2, row=1, padx=6, pady=4 )
		self.secondsEntry = ttk.Entry( self, width=8, state='disabled' )
		self.secondsEntry.grid( column=3, row=1, padx=6, pady=4 )
		helpBtn = ttk.Label( self, text='?', foreground='#445', cursor='hand2' )
		helpBtn.grid( column=4, row=1, padx=(6, 18), pady=4 )
		helpBtn.bind( '<1>', self.helpBtnClicked )
		
	def helpBtnClicked( self, event ):
		msg( 'A "Normal" loop starts the track back at the very beginning once it reaches the end, '
			 'whereas a "Custom" loop re-starts the track at the specified point after the first playthrough.\n\n'
			 'Minutes should be an integer value between 0 and 60. Seconds may be a float value between 0 and 60, '
			 'which may include decimal places for milliseconds. e.g. 10 or 32.123', 'Loop Time Input Formats', self.master )

	def toggleTrackLooping( self, includeRadioBtn=False ):

		""" Toggles state of the minutes/seconds entries in the window. """

		if self.loopTrack.get() == 2: # For 'Custom' Loops
			state = 'normal'
		else:
			state = 'disabled'
		
		for widget in self.winfo_children():
			if widget.winfo_class() == 'TEntry' or ( includeRadioBtn and widget.winfo_class() == 'TRadiobutton' ):
				widget['state'] = state

	@property
	def minute( self ):
		""" Get and validate the loop point minute entry. """
		minuteText = self.minutesEntry.get()
		if minuteText:
			minute = int( minuteText )
			if minute < 0 or minute > 60:
				raise Exception( 'minute data entry is out of bounds. Should be between 0 and 60.' )
		else:
			minute = 0
		
		return minute

	@property
	def second( self ):
		""" Get and validate the loop point second entry. """
		secondString = self.secondsEntry.get()
		if secondString:
			second = float( secondString )
			if second < 0 or second > 60:
				raise Exception( 'second data entry is out of bounds. Should be a float between 0 and 60.' )
		else:
			second = 0.0
		
		return second

	@property
	def loopArg( self ):
		""" Format an argument string for MeleeMedia. """
		loopType = self.loopTrack.get()

		if loopType == 2: # Custom loop (to a specific minute/second)
			loopArg = ' -loop 00:{:02}:{:09.6f}'.format( self.minute, self.second ) # {:09.6f} pads left up to 9 characters, with last 6 for decimal places

		elif loopType == 1: # Normal loop (from song end to very beginning)
			loopArg = ' -loop 00:00:00'

		else: # No loop
			loopArg = ''

		return loopArg


class TrackAdder( BasicWindow ):

	def __init__( self, defaultFilename, defaultHexTrackName ):

		""" The default hex track name will be empty if this is not 20XX. If it is 20XX, 
			and the default hex track name is still empty, then all slots are full."""

		BasicWindow.__init__( self, globalData.gui.root, 'Track Adder' )

		self.defaultName = defaultFilename
		self.defaultHexTrackName = defaultHexTrackName
		self.hpsFile = None
		#self.loopTrack = Tk.IntVar( value=1 )
		self.hexTrackMaxNickLen = -1

		# File chooser
		ttk.Button( self.window, text='Choose file', command=self.chooseTrackFile ).grid( column=0, columnspan=2, row=0, padx=6, pady=(14, 4) )
		self.filenameDisplay = ttk.Label( self.window, text='', wraplength=500 )
		self.filenameDisplay.grid( column=0, columnspan=2, row=1, padx=6, pady=4 )
		ttk.Separator( self.window, orient='horizontal' ).grid( column=0, columnspan=2, row=2, sticky='ew', padx=50, pady=4 )
		
		# Hex Track / Regular track selection
		if defaultHexTrackName:
			self.addAsHexTrack = Tk.BooleanVar( value=True )
			hexTrackDecisionFrame = ttk.Frame( self.window )
			ttk.Label( hexTrackDecisionFrame, text='Add as Hex Track:' ).grid( column=0, row=0, padx=6 )
			ttk.Radiobutton( hexTrackDecisionFrame, text='Yes', variable=self.addAsHexTrack, value=True, command=self.populateNameInputFrame ).grid( column=1, row=0, padx=6 )
			ttk.Radiobutton( hexTrackDecisionFrame, text='No', variable=self.addAsHexTrack, value=False, command=self.populateNameInputFrame ).grid( column=2, row=0, padx=6 )
			hexTrackDecisionFrame.grid( column=0, columnspan=2, row=3, pady=4 )
		else:
			self.addAsHexTrack = Tk.BooleanVar( value=False )

		# Disc filename entry
		self.nameInputFrame = ttk.Frame( self.window )
		self.nameInputFrame.grid( column=0, columnspan=2, row=4, padx=6, pady=4 )
		ttk.Separator( self.window, orient='horizontal' ).grid( column=0, columnspan=2, row=5, sticky='ew', padx=50, pady=4 )

		# Set loop point options (radio buttons and custom time entries)
		# self.loopPointFrame = ttk.Frame( self.window )
		# ttk.Label( self.loopPointFrame, text='Loop:' ).grid( column=0, row=0, padx=6, pady=4 )
		# ttk.Radiobutton( self.loopPointFrame, text='None', variable=self.loopTrack, value=0, command=self.toggleTrackLooping ).grid( column=1, row=0, padx=6, pady=4 )
		# ttk.Radiobutton( self.loopPointFrame, text='Normal', variable=self.loopTrack, value=1, command=self.toggleTrackLooping ).grid( column=2, row=0, padx=6, pady=4 )
		# ttk.Radiobutton( self.loopPointFrame, text='Custom', variable=self.loopTrack, value=2, command=self.toggleTrackLooping ).grid( column=3, row=0, padx=6, pady=4 )
		# ttk.Label( self.loopPointFrame, text='Minute:' ).grid( column=0, row=1, padx=6, pady=4 )
		# self.minutesEntry = ttk.Entry( self.loopPointFrame, width=4, state='disabled' )
		# self.minutesEntry.grid( column=1, row=1, padx=6, pady=4 )
		# ttk.Label( self.loopPointFrame, text='Second:' ).grid( column=2, row=1, padx=6, pady=4 )
		# self.secondsEntry = ttk.Entry( self.loopPointFrame, width=8, state='disabled' )
		# self.secondsEntry.grid( column=3, row=1, padx=6, pady=4 )
		# helpBtn = ttk.Label( self.loopPointFrame, text='?', foreground='#445', cursor='hand2' )
		# helpBtn.grid( column=4, row=1, padx=6, pady=4 )
		# helpBtn.bind( '<1>', self.helpBtnClicked )
		# self.loopPointFrame.grid( column=0, columnspan=2, row=6, padx=6, pady=20 )
		self.loopEditor = LoopEditor( self.window )
		self.loopEditor.grid( column=0, columnspan=2, row=6, padx=6, pady=20 )
		ttk.Separator( self.window, orient='horizontal' ).grid( column=0, columnspan=2, row=7, sticky='ew', padx=50, pady=4 )

		# Track name (nickname) entry
		nicknameEntryFrame = ttk.Frame( self.window )
		ttk.Label( nicknameEntryFrame, text='Track Name:' ).grid( column=0, row=0, padx=6, pady=4 )
		validationCommand = globalData.gui.root.register( self.nicknameModified )
		self.nicknameEntry = ttk.Entry( nicknameEntryFrame, width=33, validate='key', validatecommand=(validationCommand, '%P') )
		self.nicknameEntry.grid( column=1, row=0, padx=6, pady=4 )
		self.nickLengthText = ttk.Label( nicknameEntryFrame )
		self.nickLengthText.grid( column=2, row=0, padx=6, pady=4 )
		nicknameEntryFrame.grid( column=0, columnspan=2, row=8, padx=6, pady=8 )

		self.populateNameInputFrame()

		# Confirm / Cancel buttons
		ttk.Button( self.window, text='Confirm', command=self.submitFile ).grid( column=0, row=9, ipadx=0, padx=6, pady=(4, 14) )
		ttk.Button( self.window, text='Cancel', command=self.cancel ).grid( column=1, row=9, padx=6, pady=(4, 14) )

		# Move focus to this window (for keyboard control), and pause execution of the calling function until this window is closed.
		self.window.grab_set()
		globalData.gui.root.wait_window( self.window ) # Freezes the GUI until this window is closed.

	def determineMaxNickLength( self ):

		""" Checks the track number and determines how long the song description/nickname may be. """
	
		if self.addAsHexTrack.get():
			if self.hexTrackMaxNickLen == -1:
				trackNumber = int( os.path.splitext(self.defaultHexTrackName)[0], 16 )
				cssFile = globalData.disc.files.get( globalData.disc.gameId + '/MnSlChr.0sd' )
				self.hexTrackMaxNickLen = cssFile.checkMaxHexTrackNameLen( trackNumber )
			
			self.nickMaxLength = self.hexTrackMaxNickLen
		else:
			self.nickMaxLength = 42

		# Trigger the character count display to update by simulating an event
		#self.nicknameEntry.event_generate( '<<KeyPress>>' )
		self.nicknameModified( self.nicknameEntry.get().strip() )

	def nicknameModified( self, newString ):

		""" Updates the character count for the Track Name (i.e. description/nickname) entry field. 
			Must return True to validate the entered text and allow it to be displayed. """

		newStrLen = len( newString.strip() )
		self.nickLengthText['text'] = '{}/{}'.format( newStrLen, self.nickMaxLength )

		if newStrLen > self.nickMaxLength:
			self.nickLengthText['foreground'] = '#a34343' # red
		else:
			self.nickLengthText['foreground'] = '#292' # green

		return True

	def populateNameInputFrame( self ):

		""" Populates widgets for choosing whether to add as a hex track or standard file, and for entering a disc file name. 
			Called by the 'Add as Hex Track' radio buttons, as well as during initial window creation. """

		for widget in self.nameInputFrame.winfo_children():
			widget.destroy()

		if self.addAsHexTrack.get():
			#ttk.Label( self.nameInputFrame, text='Enter a hex value (0 - FF) for the new disc file name:' ).grid( column=0, columnspan=2, row=0, padx=6, pady=4 )
			ttk.Label( self.nameInputFrame, text='First empty Hex Track slot (must be added in order):' ).grid( column=0, row=0, padx=6, pady=4 )
			self.filenameLabel = ttk.Label( self.nameInputFrame, text=self.defaultHexTrackName )
			self.filenameLabel.grid( column=0, row=1, padx=6, pady=4 )
		else:
			ttk.Label( self.nameInputFrame, text='Enter a disc file name less than 30 characters:' ).grid( column=0, columnspan=2, row=0, padx=6, pady=4 )
			self.filenameLabel = ttk.Label( self.nameInputFrame, text=self.defaultName )
			self.filenameLabel.grid( column=0, row=1, padx=6, pady=4 )

			ttk.Button( self.nameInputFrame, text='Change', command=self.promptForDiscFilename ).grid( column=1, row=1, padx=6, pady=4 )

		self.determineMaxNickLength()

	# def toggleTrackLooping( self, includeRadioBtn=False ):

	# 	""" Toggles state of the minutes/seconds entries in the window. 
	# 		Called by the 'Loop' Yes/No radio buttons. """

	# 	if self.loopTrack.get() == 2: # For 'Custom' Loops
	# 		state = 'normal'
	# 	else:
	# 		state = 'disabled'
		
	# 	for widget in self.loopPointFrame.winfo_children():
	# 		if widget.winfo_class() == 'TEntry' or ( includeRadioBtn and widget.winfo_class() == 'TRadiobutton' ):
	# 			widget['state'] = state

	def promptForDiscFilename( self ):

		""" Prompt the user to enter a disc filename (not description), 
			validate it, and display it in this window if valid. """

		illegalChars = ( '-', '/', '\\', ':', '*', '?', '<', '>', '|', ' ', '\n', '\t' )
		hexTrack = self.addAsHexTrack.get()

		if hexTrack:
			charLimit = 6
			newName = getNewNameFromUser( charLimit, illegalChars, defaultText=self.defaultHexTrackName )
		else:
			charLimit = 30 # todo: invesigate. notes imply this, but what's the source?
			newName = getNewNameFromUser( charLimit, illegalChars, defaultText=self.defaultName )

		# Check that there's a name, and file extension (and that it's not too long with the extension)
		if not newName: return
		elif not newName.lower().endswith( '.hps' ):
			newName += '.hps'

			# Now that the name is longer, double-check its length (valid hex tracks def won't exceed max length)
			if len( newName ) > charLimit and not hexTrack:
				msg( 'The name is too long after adding the .hps file extension. Please choose a shorter name.', 'Filename too long', self.window )
				return

		# Check if there's already a file by this name
		isoPath = '{}/audio/{}'.format( globalData.disc.gameId, newName )
		isoFile = globalData.disc.files.get( isoPath )
		if isoFile:
			msg( "A file by that name already exists in the disc!\n\nIf you'd like to replace it, "
				 "use the 'Import' feature. Otherwise, please choose another name.", 'File already exists', self.window )
			return

		# Update this window with this new name
		if hexTrack:
			self.defaultHexTrackName = newName
		else:
			self.defaultName = newName
		self.filenameLabel['text'] = newName

	def chooseTrackFile( self ):

		""" Prompts the user to select an audio file, converts it to HPS format if 
			it is not one already, and initializes it as an HPS audio file object. """
		
		# Define formats suitable for MeleeMedia input
		fileTypeOptions = [ ( 'WAV files', '*.wav' ), ("HPS files", '*.hps'), ('DSP files', '*.dsp'), ('MP3 files', '*.mp3'), 
							('AIFF files', '*.aiff'), ('WMA files', '*.wma'), ('M4A files', '*.m4a'), ("All files", "*.*") ]

		# Prompt the user to choose a file to import
		newFilePath = tkFileDialog.askopenfilename(
			title="Choose a file to import; non-HPS files will be converted on import",
			parent=self.window,
			multiple=False,
			initialdir=globalData.getLastUsedDir( 'hps' ),
			filetypes=fileTypeOptions )

		if newFilePath: # The above will return an empty string if the user canceled
			globalData.setLastUsedDir( newFilePath, 'hps' )
			self.filenameDisplay['text'] = newFilePath

			# Disable setting of loop point if this is an HPS file
			if os.path.splitext( newFilePath )[1].lower() == '.hps':
				#self.loopTrack.set( 0 )
				#self.toggleTrackLooping( True )
				self.loopEditor.loopTrack.set( 0 )
				self.loopEditor.toggleTrackLooping( True )

			else: # Make sure the Loop radio buttons are enabled
				for widget in self.loopPointFrame.winfo_children():
					if widget.winfo_class() == 'TRadiobutton':
						widget['state'] = 'normal'

	def submitFile( self ):

		""" Collect all window selections, convert the given file to HPS format if needed, initialize the 
			audio file object (which will be picked up by the calling function), and close this window. """

		isoPath = '{}/audio/{}'.format( globalData.disc.gameId, self.filenameLabel['text'] )
		filePath = self.filenameDisplay['text']

		# Ensure the disc path is unique, and an external file has been chosen
		isoFile = globalData.disc.files.get( isoPath )
		if isoFile:
			msg( "A file by that name already exists in the disc!\n\nIf you'd like to replace it, "
				 "use the 'Import' feature. Otherwise, please choose another name.", 'File already exists', self.window )
			return
		elif not filePath:
			msg( 'No external file has been chosen to load. Click the "Choose file" button to find one.', 'No file chosen', self.window )
			return

		# Convert the file to HPS format, if needed
		if os.path.splitext( filePath )[1].lower() != '.hps':
			# Get the path to the converter executable and construct the output hps filepath
			meleeMediaExe = globalData.paths['meleeMedia']
			newFilename = os.path.basename( filePath ).rsplit( '.', 1 )[0] + '.hps'
			outputPath = os.path.join( globalData.paths['tempFolder'], newFilename )

			# if self.loopEditor.loopType == 2: # Custom loop; get values from entry fields
			# 	try:
			# 		# Get and validate the loop point minute entry
			# 		minuteText = self.minutesEntry.get()
			# 		if minuteText:
			# 			minute = int( minuteText )
			# 			if minute < 0 or minute > 60:
			# 				raise Exception( 'minute data entry is out of bounds. Should be between 0 and 60.' )
			# 		else:
			# 			minute = 0
					
			# 		# Get and validate the loop point second entry
			# 		secondString = self.secondsEntry.get()
			# 		if secondString:
			# 			second = float( secondString )
			# 			if second < 0 or second > 60:
			# 				raise Exception( 'second data entry is out of bounds. Should be a float between 0 and 60.' )
			# 		else:
			# 			second = 0.0
			# 	except Exception as err:
			# 		msg( 'Invalid input to the Loop value inputs; {}'.format(err) )
			# 		return
			# 	loopArg = ' -loop 00:{:02}:{:09.6f}'.format( minute, second ) # {:09.6f} pads left up to 9 characters, with last 6 for decimal places
			
			# elif self.loopEditor.loopType == 1: # Normal loop (from song end to very beginning)
			# 	loopArg = ' -loop 00:00:00'
			# else: # No loop
			# 	loopArg = ''
			try:
				loopArg = self.loopEditor.loopArg
			except Exception as err:
				msg( 'Invalid input for a custom loop; {}'.format(err) )
				return

			# Convert the file
			command = '"{}" "{}" "{}"{}'.format( meleeMediaExe, filePath, outputPath, loopArg )
			returnCode, output = cmdChannel( command )

			if returnCode != 0:
				globalData.gui.updateProgramStatus( 'Conversion failed; {}'.format(output) )
				msg( 'File conversion to HPS file format failed; {}'.format(output), 'Conversion Error', self.window )
				return

			filePath = outputPath

		# Initialize the new file
		try:
			self.hpsFile = MusicFile( globalData.disc, -1, -1, isoPath, extPath=filePath, source='file' )
			self.hpsFile.getData()
		except Exception as err:
			print 'Exception during file initialization;', err
			msg( 'A problem occurred during HPS file initialization; {}'.format(err), 'Initialization Error', self.window )
			self.hpsFile = None
			return

		# Parse the hex track name to check whether it's a hex track, and get its track number
		if self.addAsHexTrack.get():
			try:
				filename = self.filenameLabel['text']
				value = int( os.path.splitext(filename)[0], 16 )
				if value < 0 or value > 255: raise Exception
			except:
				msg( 'The hex track name includes non-hexadecimal characters or is too large. The number should be between 0 and 0xFF.', 'Invalid hex track name', self.window )
				self.hpsFile = None
				return

			# These will be unused by default when the file is initialized without a disc
			self.hpsFile.isHexTrack = True
			self.hpsFile.trackNumber = value

		# Get/add the nickname as a file.description
		name = self.nicknameEntry.get().strip()
		if name:
			try:
				self.hpsFile.setDescription( name, globalData.disc.gameId )
			except Exception as err:
				msg( 'Unable to set the track name/description; {}'.format(err), 'Invalid song name', self.window )
				self.hpsFile = None
				return

		self.close()

	# def helpBtnClicked( self, event ):
	# 	msg( 'A "Normal" loop starts the track back at the very beginning once it reaches the end, '
	# 		 'whereas a "Custom" loop re-starts the track at the specified point after the first playthrough.\n\n'
	# 		 'Minutes should be an integer value between 0 and 60. Seconds may be a float value between 0 and 60, '
	# 		 'which may include decimal places for milliseconds. e.g. 10 or 32.123', 'Loop Time Input Formats', self.window )

	def cancel( self ):
		self.hpsFile = None
		self.close()


class AudioEngine:

	""" Orchestrates audio start/stop/pause functionality within a separate audio-dedicated thread. """
	
	def __init__( self ):
		self.audioThread = None
		self.readPos = -1 # Read position for the currently playing audio file
		self.playbackAllowed = Event()
		self.exitAudioThread = Event()
		self.playRepeat = Event()
		self.volume = .35

	def checkForDotNetFramework( self ): #todo

		""" MeleeMedia requires .NET Framework 4.6.1 to be installed. This checks for this dependency. """

	def start( self, fileObj, callback=None, playConcurrently=False ):

		""" Stops any currently playing audio, and starts new playback in a new thread. 
			This method should return immediately, however a callback may be provided, 
			which will be run when the audio thread is done playing. """

		# if not playConcurrently:
		self.stop()

		# Convert the track to WAV format
		assert fileObj.getAsWav, 'Error; fileObj given to AudioEngine has no getAsWav method.'
		wavFilePath = fileObj.getAsWav()
		if not wavFilePath: return # Indicates an error (should have been conveyed in some way by now)

		# Reset flags to allow playback
		self.playbackAllowed.set()
		self.exitAudioThread.clear()

		# Highlight this song in the Audio Manager, if it's open
		#if globalData.gui.audioManagerTab:
		try:
			# Remove any existing tags, and add the new one
			fileTree = globalData.gui.audioManagerTab.fileTree
			tracksPlaying = fileTree.tag_has( 'playing' )
			for iid in tracksPlaying:
				fileTree.removeTag( iid, 'playing' )
			isoPath = '{}/audio/{}'.format( globalData.disc.gameId, fileObj.filename )
			fileTree.addTag( isoPath, 'playing' )
		except: pass

		# Play the audio clip in a separate thread so that it's non-blocking
		# (Yes, pyaudio has a "non-blocking" way for playback already, but that 
		# too needs to block anyway due to waiting for the thread to finish.)
		self.audioThread = Thread( target=self._playAudioHelper, args=(wavFilePath, callback, True), name=fileObj.filename )
		self.audioThread.daemon = True # Causes the audio thread to be stopped when the main program stops
		self.audioThread.start()

	def isPlayingAudio( self ):
		if self.audioThread:
			return True
		return False

	def pause( self ):
		""" The following event object must be set for the audio output stream to loop. """
		self.playbackAllowed.clear()

	def unpause( self ):
		self.playbackAllowed.set()

	def stop( self ):
		self.exitAudioThread.set()
		self.playbackAllowed.set() # If paused, make sure the loop can proceed to exit itself
		
		# Wait for the thread to end
		timeout = 0 # Failsafe to prevent possibility of an infinite loop
		while self.audioThread:
			time.sleep( .1 )
			if timeout > 3:
				print 'Thread did not exit in time!'
				return
			timeout += .1

	def reset( self ):

		""" Sets file read position in the audio data stream's write loop back to the beginning. """

		self.readPos = 0

	def _playAudioHelper( self, soundFilePath, callback=None, deleteWav=False ):

		""" Helper (thread-target) function for playSound(). Runs in a separate 
			thread to prevent audio playback from blocking main execution. """

		p = None
		wf = None
		stream = None

		try:
			# Instantiate PyAudio and open the target audio file
			p = pyaudio.PyAudio()
			wf = wave.open( soundFilePath, 'rb' )

			# Get track info and open an audio data stream
			sampleWidth = wf.getsampwidth()
			channels = wf.getnchannels()
			assert sampleWidth == 2, 'Unsupported sample width: ' + str( sampleWidth )
			assert channels == 2, 'Unsupported channel count: ' + str( channels )
			stream = p.open( format=p.get_format_from_width(sampleWidth),
								channels=channels,
								rate=wf.getframerate(),
								output=True )

			# Prepare for the data stream loop
			framesPerIter = 1024
			data = wf.readframes( framesPerIter )

			# Continuously read/write data from the file to the stream until there is no data left
			while len( data ) > 0:
				self.playbackAllowed.wait() # This will block if the playbackAllowed event is not set
				
				if self.exitAudioThread.isSet(): # Check if this thread should stop and exit
					self.exitAudioThread.clear()
					break
				elif self.readPos != -1: # Move to a new place in the file data
					wf.setpos( self.readPos )
					self.readPos = -1
				else:
					data = self._adjustVolume( data )
					stream.write( data )
					
				data = wf.readframes( framesPerIter )

				# Check if playing should start over (repeat is turned on)
				if self.playRepeat.isSet() and not len( data ) > 0:
					wf.setpos( 0 ) # Setting read position to the start of the file
					data = wf.readframes( framesPerIter )

		except Exception as err:
			soundFileName = os.path.basename( soundFilePath )
			print 'Unable to play "{}" song.'.format( soundFileName )
			print err

		# Stop the stream
		if stream:
			stream.stop_stream()
			stream.close()

		# Close PyAudio
		if p:
			p.terminate()
		
		# Close the wav file and delete it
		if wf:
			wf.close()
			if deleteWav:
				try:
					os.remove( soundFilePath )
				except: pass

		self.audioThread = None

		if callback:
			try:
				callback()
			except: pass

		# Remove 'now playing' highlighting in the Audio Manager, if it's open (todo: relocate this to main gui thread! need a real callback system)
		try:
			fileTree = globalData.gui.audioManagerTab.fileTree
			tracksPlaying = fileTree.tag_has( 'playing' )
			for iid in tracksPlaying:
				fileTree.removeTag( iid, 'playing' )
		except: pass

	def _adjustVolume( self, dataframes ):

		# Unpack the bytes data
		chunkFormat = '<' + str( len(dataframes)/2 ) + 'h'
		unpackedData = struct.unpack( chunkFormat, dataframes )

		# Multiply each value by the current volume (0-1.0 value)
		unpackedData = [sample * self.volume for sample in unpackedData]

		# Re-pack the data as raw bytes and return it
		return struct.pack( chunkFormat, *unpackedData )


class AudioControlModule( object, ttk.Frame ):

	def __init__( self, parent, audioEngine, audioFile=None, *args, **kwargs ):
		ttk.Frame.__init__( self, parent, *args, **kwargs )

		# Add the primary buttons
		self.playBtn = ttk.Button( self, text='Pla', width=4, command=self.playAudio )
		self.playBtn.grid( column=0, row=0 )
		self.stopBtn = ttk.Button( self, text='Stp', width=3, command=audioEngine.stop )
		self.stopBtn.grid( column=1, row=0 )
		self.resetBtn = ttk.Button( self, text='Rst', width=3, command=audioEngine.reset )
		self.resetBtn.grid( column=2, row=0 )
		self.repeatModeVar = Tk.IntVar()
		ttk.Checkbutton( self, text='Repeat', variable=self.repeatModeVar, command=self.toggleRepeatMode ).grid( column=3, row=0 )

		self.audioEngine = audioEngine
		self.audioFile = audioFile

	@property
	def audioFile( self ):
		return self._audioFile

	@audioFile.setter
	def audioFile( self, audioFile ):

		""" Updates the status of the play/pause button when the target file to play is changed. """

		self._audioFile = audioFile

		if not audioFile: # Make no change to the play/pause button
			return

		if self.audioEngine.isPlayingAudio():
			# Check if this is a different song than the one that's currently playing
			try:
				if self.audioEngine.audioThread.name != self.audioFile.filename:
					self.showPlayBtn()
				else: # Must be the same file that's already playing
					self.showPauseBtn()
			except: pass # The button may not exist yet

	def showPlayBtn( self ):
		self.playBtn['text'] = 'Pla'

	def showPauseBtn( self ):
		self.playBtn['text'] = 'Pau'

	def playAudio( self, event=None ):

		""" Starts playing audio if it is not already playing. If audio is already playing, it is 
			stopped if the track has been changed, or it is paused if it's still the same track. 
			Has an unused 'event' arg for use in calling this method from a bound click event. """

		if not self.audioFile:
			print 'No file currently selected'
			return

		# Start a new audio thread if one is not already running
		if self.audioEngine.isPlayingAudio(): # An audio thread is already present; pause/play the audio there
			# Check if the current audio thread is for a previously selected file (and therefore should be ended)
			if self.audioEngine.audioThread.name != self.audioFile.filename:
				self.audioEngine.stop()

			elif self.audioEngine.playbackAllowed.isSet(): # Audio is not paused
				self.audioEngine.pause()
				self.showPlayBtn()
				return

			else: # Audio is currently paused; start it again
				self.audioEngine.unpause()
				self.showPauseBtn()
				return

		self.audioEngine.start( self.audioFile, self.showPlayBtn )
		self.showPauseBtn() # The above will return immediately; show the pause button while playback happens

	def toggleRepeatMode( self ):

		""" Wrapper for the "Repeat" checkbox in the GUI. Using a variable such as an IntVar (which is tied to 
			the GUI) in another thread can cause severe problems, so this method instead uses the IntVar variable 
			to control an event object, which is then used to control looping in the thread playing audio. """

		if self.repeatModeVar.get():
			self.audioEngine.playRepeat.set()
		else:
			self.audioEngine.playRepeat.clear()