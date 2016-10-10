'''
 ====================================================================
 Copyright (c) 2016 Barry A Scott.  All rights reserved.

 This software is licensed as described in the file LICENSE.txt,
 which you should have received as part of this distribution.

 ====================================================================

    wb_hg_log_history.py


'''
import pytz

from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

import wb_tracked_qwidget
import wb_main_window
import wb_ui_components
import wb_table_view

from wb_background_thread import thread_switcher

#------------------------------------------------------------
#
#   WbHgLogHistoryView - show the commits from the log model
#
#------------------------------------------------------------
#
#   add tool bars and menu for use in the log history window
#
class HgLogHistoryWindowComponents(wb_ui_components.WbMainWindowComponents):
    def __init__( self, factory ):
        super().__init__( 'hg', factory )

    def setupToolBarAtRight( self, addToolBar, addTool ):
        act = self.ui_actions

        # ----------------------------------------
        t = addToolBar( T_('hg info') )
        addTool( t, T_('Diff'), act.tableActionHgDiffLogHistory, act.enablerTableHgDiffLogHistory, 'toolbar_images/diff.png' )
        #addTool( t, T_('Annotate'), act.tableActionHgAnnotateLogHistory, act.enablerTableHgAnnotateLogHistory )

    def setupTableContextMenu( self, m, addMenu ):
        super().setupTableContextMenu( m, addMenu )

        act = self.ui_actions

        m.addSection( T_('Diff') )
        addMenu( m, T_('Diff'), act.tableActionHgDiffLogHistory, act.enablerTableHgDiffLogHistory, 'toolbar_images/diff.png' )

    def deferedLogHistoryProgress( self ):
        return self.app.deferRunInForeground( self.__logHistoryProgress )

    def __logHistoryProgress( self, count, total ):
        if total > 0:
            if count == 0:
                self.progress.start( '%(count)s of %(total)d commits loaded. %(percent)d%%', total )

            else:
                self.progress.incEventCount()


class WbHgLogHistoryView(wb_main_window.WbMainWindow, wb_tracked_qwidget.WbTrackedModeless):
    focus_is_in_names = ('commits', 'changes')
    def __init__( self, app, title ):
        self.app = app
        self._debug = self.app._debug_options._debugLogHistory

        super().__init__( app, app._debug_options._debugMainWindow )

        self.current_commit_selections = []
        self.current_file_selection = []

        self.filename = None
        self.hg_project = None

        self.ui_component = HgLogHistoryWindowComponents( self.app.getScmFactory( 'hg' ) )

        self.log_model = WbHgLogHistoryModel( self.app )
        self.changes_model = WbHgChangedFilesModel( self.app )

        self.setWindowTitle( title )
        self.setWindowIcon( self.app.getAppQIcon() )

        self.code_font = self.app.getCodeFont()

        #----------------------------------------
        self.log_table = WbLogTableView( self )
        self.log_table.setSelectionBehavior( self.log_table.SelectRows )
        self.log_table.setSelectionMode( self.log_table.ExtendedSelection )
        self.log_table.setModel( self.log_model )

        # size columns
        em = self.app.fontMetrics().width( 'm' )
        self.log_table.setColumnWidth( self.log_model.col_author, em*16 )
        self.log_table.setColumnWidth( self.log_model.col_date, em*20 )
        self.log_table.setColumnWidth( self.log_model.col_message, em*40 )

        #----------------------------------------
        self.commit_message = QtWidgets.QTextEdit()
        self.commit_message.setReadOnly( True )
        self.commit_message.setCurrentFont( self.code_font )

        #----------------------------------------
        self.changeset_id = QtWidgets.QLineEdit()
        self.changeset_id.setReadOnly( True )
        self.changeset_id.setFont( self.code_font )

        #----------------------------------------
        self.changes_table = WbChangesTableView( self )
        self.changes_table.setSelectionBehavior( self.changes_table.SelectRows )
        self.changes_table.setSelectionMode( self.changes_table.SingleSelection )
        self.changes_table.setModel( self.changes_model )

        # size columns
        self.changes_table.setColumnWidth( self.changes_model.col_action, em*6 )
        self.changes_table.setColumnWidth( self.changes_model.col_path, em*60 )
        self.changes_table.setColumnWidth( self.changes_model.col_copyfrom, em*60 )

        #------------------------------------------------------------
        self.changed_files_layout = QtWidgets.QVBoxLayout()
        self.changed_files_layout.addWidget( QtWidgets.QLabel( T_('Changed Files') ) )
        self.changed_files_layout.addWidget( self.changes_table )

        self.changed_files = QtWidgets.QWidget()
        self.changed_files.setLayout( self.changed_files_layout )

        #----------------------------------------
        self.commit_info_layout = QtWidgets.QVBoxLayout()
        self.commit_info_layout.addWidget( self.log_table )
        self.commit_info_layout.addWidget( QtWidgets.QLabel( T_('Changeset') ) )
        self.commit_info_layout.addWidget( self.changeset_id )
        self.commit_info_layout.addWidget( QtWidgets.QLabel( T_('Commit Message') ) )
        self.commit_info_layout.addWidget( self.commit_message )

        self.commit_info = QtWidgets.QWidget()
        self.commit_info.setLayout( self.commit_info_layout )

        #----------------------------------------
        self.v_split = QtWidgets.QSplitter()
        self.v_split.setOrientation( QtCore.Qt.Vertical )

        self.v_split.addWidget( self.log_table )
        self.v_split.setStretchFactor( self.v_split.count()-1, 15 )
        self.v_split.addWidget( self.commit_info )
        self.v_split.setStretchFactor( self.v_split.count()-1, 6 )
        self.v_split.addWidget( self.changed_files )
        self.v_split.setStretchFactor( self.v_split.count()-1, 9 )

        self.setCentralWidget( self.v_split )

        ex = self.app.fontMetrics().lineSpacing()
        self.resize( 70*em, 40*ex )

        self.ui_component.setTopWindow( self.app.top_window )
        self.ui_component.setMainWindow( self, None )

        # setup the chrome
        self.setupMenuBar( self.menuBar() )
        self.setupToolBar()
        self.__setupTableContextMenu()

    def completeInit( self ):
        self._debug( 'completeInit()' )
        # set focus
        self.log_table.setFocus()

    def setupMenuBar( self, mb ):
        self.ui_component.setupMenuBar( mb, self._addMenu )

    def __setupTableContextMenu( self ):
        self._debug( '__setupTableContextMenu' )

        # --- setup scm_type specific menu

        m = QtWidgets.QMenu( self )

        self.ui_component.setupTableContextMenu( m, self._addMenu )

    def setupToolBar( self ):
        # --- setup scm_type specific tool bars
        self.ui_component.setupToolBarAtRight( self._addToolBar, self._addTool )

    def isScmTypeActive( self, scm_type ):
        return scm_type == 'hg'

    @thread_switcher
    def showCommitLogForRepository_Bg( self, hg_project, options ):
        self.filename = None
        self.hg_project = hg_project

        yield self.app.switchToBackground

        self.log_model.loadCommitLogForRepository( self.ui_component.deferedLogHistoryProgress(), hg_project, options.getLimit(), options.getSince(), options.getUntil() )

        yield self.app.switchToForeground

        self.log_table.resizeColumnToContents( self.log_model.col_date )

        self.ui_component.progress.end()
        self.updateEnableStates()
        self.show()

    @thread_switcher
    def showCommitLogForFile_Bg( self, hg_project, filename, options ):
        self.filename = filename
        self.hg_project = hg_project

        yield self.app.switchToBackground

        self.log_model.loadCommitLogForFile( self.ui_component.deferedLogHistoryProgress(), hg_project, filename, options.getLimit(), options.getSince(), options.getUntil() )

        yield self.app.switchToForeground

        self.log_table.resizeColumnToContents( self.log_model.col_date )

        self.ui_component.progress.end()
        self.updateEnableStates()
        self.show()

    def selectionChangedCommit( self ):
        self.current_commit_selections = [index.row() for index in self.log_table.selectedIndexes() if index.column() == 0]

        if len(self.current_commit_selections) == 0:
            self.updateEnableStates()
            return

        self.current_commit_selections.sort()

        node = self.log_model.commitNode( self.current_commit_selections[0] )

        self.changeset_id.clear()
        self.changeset_id.setText( '%d' % (node.rev,) )

        self.commit_message.clear()
        self.commit_message.insertPlainText( node.message )

        self.changes_model.loadChanges( node.all_changed_files )

        self.updateEnableStates()

    def selectionChangedFile( self ):
        self.current_file_selection = [index.row() for index in self.changes_table.selectedIndexes() if index.column() == 0]
        self.updateEnableStates()
        if len(self.current_file_selection) == 0:
            return

        node = self.changes_model.changesNode( self.current_file_selection[0] )

class WbLogTableView(wb_table_view.WbTableView):
    def __init__( self, main_window ):
        self.main_window = main_window

        self._debug = main_window._debug

        super().__init__()

    def selectionChanged( self, selected, deselected ):
        self._debug( 'WbLogTableView.selectionChanged()' )

        self.main_window.selectionChangedCommit()

        # allow the table to redraw the selected row highlights
        super().selectionChanged( selected, deselected )

    def focusInEvent( self, event ):
        super().focusInEvent( event )

        self.main_window.setFocusIsIn( 'commits' )

class WbHgLogHistoryModel(QtCore.QAbstractTableModel):
    col_author = 0
    col_date = 1
    col_message = 2

    column_titles = (U_('Author'), U_('Date'), U_('Message'))

    def __init__( self, app ):
        self.app = app

        self._debug = self.app._debug_options._debugLogHistory

        super().__init__()

        self.all_commit_nodes  = []

    def loadCommitLogForRepository( self, progress_callback, hg_project, limit, since, until ):
        self.beginResetModel()
        self.all_commit_nodes = hg_project.cmdCommitLogForRepository( limit, since, until )
        self.endResetModel()

    def loadCommitLogForFile( self, progress_callback, hg_project, filename, limit, since, until ):
        self.beginResetModel()
        self.all_commit_nodes = hg_project.cmdCommitLogForFile( filename, limit, since, until )
        self.endResetModel()

    def revisionForRow( self, row ):
        node = self.all_commit_nodes[ row ]
        return node.rev

    def dateStringForRow( self, row ):
        node = self.all_commit_nodes[ row ]
        return self.app.formatDatetime( node.date.replace( tzinfo=pytz.utc ) )

    def rowCount( self, parent ):
        return len( self.all_commit_nodes )

    def columnCount( self, parent ):
        return len( self.column_titles )

    def headerData( self, section, orientation, role ):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return T_( self.column_titles[section] )

            if orientation == QtCore.Qt.Vertical:
                return ''

        elif role == QtCore.Qt.TextAlignmentRole and orientation == QtCore.Qt.Horizontal:
            return QtCore.Qt.AlignLeft

        return None

    def commitNode( self, row ):
        return self.all_commit_nodes[ row ]

    def data( self, index, role ):
        if role == QtCore.Qt.UserRole:
            return self.all_commit_nodes[ index.row() ]

        if role == QtCore.Qt.DisplayRole:
            node = self.all_commit_nodes[ index.row() ]

            col = index.column()

            if col == self.col_author:
                return node.author

            elif col == self.col_date:
                dt = node.date.replace( tzinfo=pytz.utc )
                return self.app.formatDatetime( dt )

            elif col == self.col_message:
                return node.message.split('\n')[0]

            assert False

        return None

class WbChangesTableView(wb_table_view.WbTableView):
    def __init__( self, main_window ):
        self.main_window = main_window

        self._debug = main_window._debug

        super().__init__()

    def selectionChanged( self, selected, deselected ):
        self._debug( 'WbChangesTableView.selectionChanged()' )

        # allow the table to redraw the selected row highlights
        super().selectionChanged( selected, deselected )

        self.main_window.selectionChangedFile()

    def focusInEvent( self, event ):
        super().focusInEvent( event )

        self.main_window.setFocusIsIn( 'changes' )

class WbHgChangedFilesModel(QtCore.QAbstractTableModel):
    col_action = 0
    col_path = 1
    col_copyfrom = 2

    column_titles = (U_('Action'), U_('Filename'), U_('Copied from'))

    def __init__( self, app ):
        self.app = app

        self._debug = self.app._debug_options._debugLogHistory

        super().__init__()

        self.all_changes  = []

    def loadChanges( self, all_changed_paths ):
        self.beginResetModel()
        self.all_changes = all_changed_paths
        self.endResetModel()

    def rowCount( self, parent ):
        return len( self.all_changes )

    def columnCount( self, parent ):
        return len( self.column_titles )

    def headerData( self, section, orientation, role ):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return T_( self.column_titles[section] )

            if orientation == QtCore.Qt.Vertical:
                return ''

        elif role == QtCore.Qt.TextAlignmentRole and orientation == QtCore.Qt.Horizontal:
            return QtCore.Qt.AlignLeft

        return None

    def changesNode( self, row ):
        return self.all_changes[ row ]

    def data( self, index, role ):
        if role == QtCore.Qt.UserRole:
            return self.all_changes[ index.row() ]

        if role == QtCore.Qt.DisplayRole:
            type_, filename = self.all_changes[ index.row() ]
            old_filename = None

            col = index.column()

            if col == self.col_action:
                return type_

            elif col == self.col_path:
                return filename

            elif col == self.col_copyfrom:
                if type_ in ('A', 'D', 'M'):
                    return ''

                else:
                    return old_filename

            assert False

        return None
