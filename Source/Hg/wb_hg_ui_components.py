'''
 ====================================================================
 Copyright (c) 2003-2016 Barry A Scott.  All rights reserved.

 This software is licensed as described in the file LICENSE.txt,
 which you should have received as part of this distribution.

 ====================================================================

    wb_hg_ui_components.py.py

'''
import shutil

import hglib

import wb_ui_components
import wb_hg_project


class HgMainWindowComponents(wb_ui_components.WbMainWindowComponents):
    def __init__( self, factory ):
        self.all_visible_table_columns = None

        super().__init__( 'hg', factory )

    def setTopWindow( self, top_window ):
        super().setTopWindow( top_window )

        prefs = self.app.prefs.hg
        if prefs.program is not None:
            hglib.HGPATH = str( prefs.program )

        self.log.info( T_('Hg using program %s') % (shutil.which( hglib.HGPATH ),) )

    def createProject( self, project ):
        tm = self.table_view.table_model
        self.all_visible_table_columns = (tm.col_status, tm.col_name, tm.col_date)

        if shutil.which( hglib.HGPATH ) is None:
            self.log.error( T_('Mercurial "hg" command line tool not found') )
            return None

        try:
            return wb_hg_project.HgProject( self.app, project, self )

        except hglib.error.ServerError as e:
            self.app.log.error( T_('Failed to add Hg repo %s') % (project.path,) )
            self.app.log.error( T_('hg error: %s') % (e,) )
            return None

    #------------------------------------------------------------
    def addProjectPreInitWizardHandler( self, name, url, wc_path ):
        self.log.infoheader( T_('Initialise Hg repository in %s') % (wc_path,) )
        self.setStatusAction( T_('Init %(project)s') %
                                    {'project': name} )
        self.progress.start( T_('No progress available for hg') )

    # runs on the background thread
    def addProjectInitWizardHandler_Bg( self, wc_path ):
        hg_project = wb_hg_project.HgProject( self.app, None, self )
        try:
            hg_project.cmdInit( wc_path,
                self.deferRunInForeground( self.ui_actions.hgOutputHandler ),
                self.deferRunInForeground( self.ui_actions.hgErrorHandler ),
                self.ui_actions.hgCredentialsPrompt,
                self.ui_actions.hgAuthFailed )
            return True

        except hglib.error.ServerError as e:
            self.app.log.error( T_('Failed to init Hg repo %r') % (hg_project.path,) )
            self.app.log.error( T_('hg error: %s') % (e,) )
            return False

    def addProjectPostInitWizardHandler( self ):
        self.progress.end()
        self.setStatusAction()

    #------------------------------------------------------------
    def addProjectPreCloneWizardHandler( self, name, url, wc_path ):
        self.log.infoheader( T_('Cloning Hg repository %(url)s into %(path)s') %
                                    {'url': url, 'path': wc_path} )
        self.setStatusAction( T_('Clone %(project)s') %
                                    {'project': name} )
        self.progress.start( T_('No progress available for hg') )

    # runs on the background thread
    def addProjectCloneWizardHandler_Bg( self, name, url, wc_path, scm_state ):
        try:
            hg_project = wb_hg_project.HgProject( self.app, None, self )
            hg_project.cmdClone( url, wc_path,
                self.deferRunInForeground( self.ui_actions.hgOutputHandler ),
                self.deferRunInForeground( self.ui_actions.hgErrorHandler ),
                self.ui_actions.hgCredentialsPrompt,
                self.ui_actions.hgAuthFailed )
            return True

        except hglib.error.ServerError as e:
            self.app.log.error( T_('Failed to clone Hg repo from %(url)s into %(path)s') %
                                {'url': url
                                ,'path': wc_path} )
            self.app.log.error( 'hg error: %s' % (e,) )
            return False

    def addProjectPostCloneWizardHandler( self ):
        self.progress.end()
        self.setStatusAction()

    #------------------------------------------------------------
    def about( self ):
        if shutil.which( hglib.HGPATH ) is None:
            return ['Mercurial "hg" command line tool not found']

        else:
            return [wb_hg_project.HgVersion()]

    def setupDebug( self ):
        self.debugLog = self.main_window.app.debug_options.debugLogHgUi

    def setupMenuBar( self, mb, addMenu ):
        act = self.ui_actions

        # ----------------------------------------
        m = mb.addMenu( T_('&Hg Information') )
        self.all_menus.append( m )

        addMenu( m, T_('Diff TIP vs. Working'), act.treeTableActionHgDiffHeadVsWorking, act.enablerHgDiffHeadVsWorking, 'toolbar_images/diff.png' )
        m.addSeparator()
        addMenu( m, T_('Annotate'), act.tableActionHgAnnotate_Bg, act.enablerTableHgAnnotate )
        m.addSeparator()
        addMenu( m, T_('Status'), act.treeActionHgStatus_Bg )
        m.addSeparator()
        addMenu( m, T_('Commit History…'), act.treeTableActionHgLogHistory_Bg, act.enablerHgLogHistory, 'toolbar_images/history.png' )


        # ----------------------------------------
        m = mb.addMenu( T_('&Hg Actions') )
        self.all_menus.append( m )

        addMenu( m, T_('Add'), act.tableActionHgAdd_Bg, act.enablerHgFilesAdd, 'toolbar_images/add.png' )

        m.addSeparator()
        addMenu( m, T_('Revert'), act.tableActionHgRevert_Bg, act.enablerHgFilesRevert, 'toolbar_images/revert.png' )
        addMenu( m, T_('Delete…'), act.tableActionHgDelete_Bg, act.main_window.table_view.enablerTableFilesExists )

        m.addSeparator()
        addMenu( m, T_('Commit…'), act.treeActionHgCommit, act.enablerHgCommit, 'toolbar_images/commit.png' )

        m.addSeparator()
        addMenu( m, T_('Push'), act.treeActionHgPush_Bg, act.enablerHgPush, 'toolbar_images/push.png' )
        addMenu( m, T_('Pull'), act.treeActionHgPull_Bg, icon_name='toolbar_images/pull.png' )

        if hasattr( self, 'treeActionHgDebug1' ):
            m = mb.addMenu( T_('&Hg Debug') )
            self.all_menus.append( m )
            addMenu( m, T_('Debug 1'), act.treeActionHgDebug1 )

    def setupToolBarAtLeft( self, addToolBar, addTool ):
        if self.app.isDarkMode():
            colour = '#cc0000'
        else:
            colour = '#cc0000'
        t = addToolBar( T_('hg logo'), style='font-size: 20pt; width: 40px; color: %s' % (colour,) )
        self.all_toolbars.append( t )

        addTool( t, 'Hg', self.main_window.projectActionSettings )

    def setupToolBarAtRight( self, addToolBar, addTool ):
        act = self.ui_actions

        # ----------------------------------------
        t = addToolBar( T_('hg info') )
        self.all_toolbars.append( t )

        addTool( t, T_('Diff'), act.treeTableActionHgDiffSmart, act.enablerHgDiffSmart, 'toolbar_images/diff.png' )
        addTool( t, T_('Commit History'), act.treeTableActionHgLogHistory_Bg, act.enablerHgLogHistory, 'toolbar_images/history.png' )

        # ----------------------------------------
        t = addToolBar( T_('hg state') )
        self.all_toolbars.append( t )

        addTool( t, T_('Add'), act.tableActionHgAdd_Bg, act.enablerHgFilesAdd, 'toolbar_images/add.png' )
        t.addSeparator()
        addTool( t, T_('Revert'), act.tableActionHgRevert_Bg, act.enablerHgFilesRevert, 'toolbar_images/revert.png' )
        addTool( t, T_('Commit'), act.treeActionHgCommit, act.enablerHgCommit, 'toolbar_images/commit.png' )
        t.addSeparator()
        addTool( t, T_('Push'), act.treeActionHgPush_Bg, act.enablerHgPush, 'toolbar_images/push.png' )
        addTool( t, T_('Pull'), act.treeActionHgPull_Bg, icon_name='toolbar_images/pull.png' )

    def setupTableContextMenu( self, m, addMenu ):
        super().setupTableContextMenu( m, addMenu )

        act = self.ui_actions

        m.addSection( T_('Diff') )
        addMenu( m, T_('Diff TIP vs. Working'), act.tableActionHgDiffHeadVsWorking, act.enablerHgDiffHeadVsWorking, 'toolbar_images/diff.png' )
        m.addSeparator()
        addMenu( m, T_('Annotate'), act.tableActionHgAnnotate_Bg, act.enablerTableHgAnnotate )

        m.addSection( T_('Hg Actions') )
        addMenu( m, T_('Revert'), act.tableActionHgRevert_Bg, act.enablerHgFilesRevert, 'toolbar_images/revert.png' )
        m.addSeparator()
        addMenu( m, T_('Delete…'), act.tableActionHgDelete_Bg, act.main_window.table_view.enablerTableFilesExists )

    def setupTreeContextMenu( self, m, addMenu ):
        super().setupTreeContextMenu( m, addMenu )

        act = self.ui_actions

        m.addSection( T_('Diff') )
        addMenu( m, T_('Diff HEAD vs. Working'), act.treeActionHgDiffHeadVsWorking, act.enablerHgDiffHeadVsWorking, 'toolbar_images/diff.png' )
