'''

 ====================================================================
 Copyright (c) 2003-2016 Barry A Scott.  All rights reserved.

 This software is licensed as described in the file LICENSE.txt,
 which you should have received as part of this distribution.

 ====================================================================

    wb_logging.py

    based on code from PySVN Workbench

'''
import sys
import os
import logging

import wb_platform_specific

from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

class AppLoggingMixin:
    def __init__( self ):
        self.log = None
        self.trace = None

    def setupLogging( self ):
        name = ''.join( self.app_name_parts )
        self.log = logging.getLogger( name )
        self.trace = logging.getLogger( '%s.Trace' % (name,) )

        if self.debugEnabled():
            self.log.setLevel( logging.DEBUG )
        else:
            self.log.setLevel( logging.INFO )

        if self.traceEnabled():
            self.trace.setLevel( logging.INFO )
        else:
            self.trace.setLevel( logging.CRITICAL )

        log_filename = wb_platform_specific.getLogFilename()

        # keep 10 logs of 100K each
        handler = RotatingFileHandler( str( log_filename ), 'a', 100*1024, 10 )
        formatter = logging.Formatter( '%(asctime)s %(levelname)s %(message)s' )
        handler.setFormatter( formatter )
        self.log.addHandler( handler )

        if self.logToStdOut():
            handler = StdoutLogHandler()
            formatter = logging.Formatter( '%(asctime)s %(levelname)s %(message)s' )
            handler.setFormatter( formatter )
            self.log.addHandler( handler )

            handler = StdoutLogHandler()
            formatter = logging.Formatter( '%(asctime)s %(levelname)s %(message)s' )
            handler.setFormatter( formatter )
            self.trace.addHandler( handler )

        self.log.debug( 'Debug is enabled' )
        self.trace.info( 'Trace enabled' )

class StdoutLogHandler(logging.Handler):
    def __init__( self ):
        logging.Handler.__init__( self )

    def emit( self, record ):
        try:
            msg = self.format( record ) + '\n'

            sys.__stdout__.write( msg )

        except:
            self.handleError( record )

#--------------------------------------------------------------------------------
class WbLog:
    def __init__( self, app ):
        self.app = app
        self.__log_widget = WbLogTextWidget( self.app )

        # Redirect the console IO to this panel
        sys.stdin = wb_platform_specific.getNullDevice().open( 'r' )
        if self.app.stdIoRedirect():
            sys.stdout = self
            sys.stderr = self

        # Redirect log to the Log panel
        log_handler = LogHandler( self.__log_widget )
        self.app.log.addHandler( log_handler )

    def logWidget( self ):
        return self.__log_widget

    def clearLog( self ):
        self.__log_widget.clear()

    #---------- look like a file object -------------------------
    def write( self, string ):
        # only allowed to use GUI objects on the foreground thread
        if not self.app.isMainThread():
            self.app.foregroundProcess( self.write, (string,) )
            return

        if string.startwith( 'Error:' ):
            self.__log_widget.writeError( string )

        elif string.startswith( 'Info:' ):
            self.__log_widget.writeInfo( string )

        elif string.startswith( 'Warning:' ):
            self.__log_widget.writeWarning( string )

        elif string.startswith( 'Crit:' ):
            self.__log_widget.writeCritical( string )

        else:
            self.__log_widget.writeNormal( string )

        if not self.app.isStdIoRedirect():
            sys.__stdout__.write(  string  )

    def close( self ):
        pass

#--------------------------------------------------------------------------------
class LogHandler(logging.Handler):
    def __init__( self, log_ctrl ):
        self.log_ctrl = log_ctrl
        logging.Handler.__init__( self )

    def emit( self, record ):
        msg = self.format( record ) + '\n'
        level = record.levelno

        if level >= logging.CRITICAL:
            self.log_ctrl.writeCritical( msg )

        elif level >= logging.ERROR:
            self.log_ctrl.writeError( msg )

        elif level >= logging.WARNING:
            self.log_ctrl.writeWarning( msg )

        elif level >= logging.INFO:
            self.log_ctrl.writeInfo( msg )

        elif level >= logging.DEBUG:
            self.log_ctrl.writeDebug( msg )

        else:
            self.log_ctrl.writeError( msg )

#--------------------------------------------------------------------------------
class WbLogTextWidget(QtWidgets.QTextEdit):
    style_normal = 0
    style_error = 1
    style_info = 2
    style_warning = 3
    style_critical = 4
    style_debug = 5

    all_style_colours = (
        (style_normal,   '#000000', '#ffffff'),
        (style_error,    '#DC143C', '#ffffff'),    # Crimson
        (style_info,     '#191970', '#ffffff'),    # Midnight Blue
        (style_warning,  '#008000', '#ffffff'),    # Green
        (style_critical, '#BA55D3', '#ffffff'),    # Medium Orchid
        (style_debug,    '#191970', '#cccccc'),
        )

    def __init__( self, app ):
        self.app = app

        self.all_text_formats = {}
        for style, fg_colour, bg_colour in self.all_style_colours:
            format = QtGui.QTextCharFormat()
            format.setForeground( QtGui.QBrush( QtGui.QColor( fg_colour ) ) )
            format.setBackground( QtGui.QBrush( QtGui.QColor( bg_colour ) ) )
            self.all_text_formats[ style ] = format

        super().__init__()
        self.setReadOnly( True )

    def writeStyledText( self, text, style ):
        self.moveCursor( QtGui.QTextCursor.End )

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setCharFormat( self.all_text_formats[ style ] )
        cursor.insertText( text )
        cursor.endEditBlock()

        self.ensureCursorVisible()

    def writeNormal( self, text ):
        self.writeStyledText( text, self.style_normal )

    def writeError( self, text ):
        self.writeStyledText( text, self.style_error )

    def writeInfo( self, text ):
        self.writeStyledText( text, self.style_info )

    def writeWarning( self, text ):
        self.writeStyledText( text, self.style_warning )

    def writeCritical( self, text ):
        self.writeStyledText( text, self.style_critical )

    def writeDebug( self, text ):
        self.writeStyledText( text, self.style_debug )

    def clearText( self ):
        self.clear()

#--------------------------------------------------------------------------------
#
#    RotatingFileHandler - based on python lib class
#
#--------------------------------------------------------------------------------
class RotatingFileHandler(logging.FileHandler):
    def __init__(self, filename, mode="a", maxBytes=0, backupCount=0):
        """
        Open the specified file and use it as the stream for logging.

        By default, the file grows indefinitely. You can specify particular
        values of maxBytes and backupCount to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly maxBytes in
        length. If backupCount is >= 1, the system will successively create
        new files with the same pathname as the base file, but with extensions
        ".1", ".2" etc. appended to it. For example, with a backupCount of 5
        and a base file name of "app.log", you would get "app.log",
        "app.log.1", "app.log.2", ... through to "app.log.5". The file being
        written to is always "app.log" - when it gets filled up, it is closed
        and renamed to "app.log.1", and if files "app.log.1", "app.log.2" etc.
        exist, then they are renamed to "app.log.2", "app.log.3" etc.
        respectively.

        If maxBytes is zero, rollover never occurs.
        """
        logging.FileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        if maxBytes > 0:
            self.mode = "a"

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        self.stream.close()
        if self.backupCount > 0:
            prefix, suffix = os.path.splitext( self.baseFilename )
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d%s" % (prefix, i, suffix)
                dfn = "%s.%d%s" % (prefix, i+1, suffix)
                if os.path.exists(sfn):
                    #print "%s -> %s" % (sfn, dfn)
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.baseFilename, dfn)

        self.stream = open(self.baseFilename, "w")

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in setRollover().
        """
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            try:
                self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
                if self.stream.tell() + len(msg) >= self.maxBytes:
                    self.doRollover()

            except ValueError:
                # on Windows we get "ValueError: I/O operation on closed file"
                # when a second copy of workbench is run
                self.doRollover()

        logging.FileHandler.emit(self, record)